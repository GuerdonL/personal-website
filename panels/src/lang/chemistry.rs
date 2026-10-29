//! Chemistry: what molecules do when they meet (SPEC §3.2–3.4).
//!
//! This module owns the *rules*. Machines own the *strategy* and must call
//! only [`react`] and [`settle`]; they never hard-code a reaction.

use super::value::{Closure, Value};

/// What two molecules do when they meet: a finished value, or work the
/// machine must do (SPEC §3.2).
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Reaction {
    Value(Value),
    /// Evaluate `closure.body`'s children under `closure.extended(arg)`,
    /// then settle them. The result is the value of the panel this happened in.
    Apply {
        closure: Closure,
        arg: Value,
    },
}

/// The complete pairwise chemistry. Commutative by construction; never
/// evaluates anything.
pub fn react(a: &Value, b: &Value) -> Option<Reaction> {
    use Value::*;
    match (a, b) {
        (Add(m), Add(n)) => Some(Reaction::Value(Add(m + n))),
        (Add(n), Num(x)) | (Num(x), Add(n)) => Some(Reaction::Value(Num(x + n))),
        (Closure(c), d) | (d, Closure(c)) if d.is_datum() => Some(Reaction::Apply {
            closure: c.clone(),
            arg: d.clone(),
        }),
        _ => None,
    }
}

/// The outcome of settling a panel's children (SPEC §3.3).
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Settled {
    Value(Value),
    /// The panel's value is the result of this application.
    Apply {
        closure: Closure,
        arg: Value,
    },
}

/// Turn the evaluated children of a panel into the panel's value, or into
/// the one application that produces it.
///
/// 1. Coalesce transformers until no two react.
/// 2. If exactly one transformer and exactly one datum remain and they react,
///    that reaction is the answer.
/// 3. One molecule left ⇒ it is the value; otherwise the canonical `Bag`.
///
/// Order-independent for the v0 chemistry; see SPEC §3.4 for the obligation
/// this places on any extension.
pub fn settle(molecules: Vec<Value>) -> Settled {
    let (mut transformers, mut data): (Vec<Value>, Vec<Value>) =
        molecules.into_iter().partition(Value::is_transformer);

    // 1. Coalesce transformers.
    transformers = coalesce(transformers);

    // 2. Apply.
    if transformers.len() == 1 && data.len() == 1 {
        match react(&transformers[0], &data[0]) {
            Some(Reaction::Value(v)) => return Settled::Value(v),
            Some(Reaction::Apply { closure, arg }) => return Settled::Apply { closure, arg },
            None => {}
        }
    }

    // 3. Unwrap or bag.
    let mut rest = transformers;
    rest.append(&mut data);
    Settled::Value(if rest.len() == 1 {
        rest.pop().unwrap()
    } else {
        Value::bag(rest)
    })
}

/// Repeatedly react any two transformers whose reaction is itself a value,
/// until none do. (An `Apply` never arises here: both members are
/// transformers, and a closure needs a datum.)
fn coalesce(mut items: Vec<Value>) -> Vec<Value> {
    'outer: loop {
        for i in 0..items.len() {
            for j in (i + 1)..items.len() {
                if let Some(Reaction::Value(v)) = react(&items[i], &items[j]) {
                    items.swap_remove(j);
                    items.swap_remove(i);
                    items.push(v);
                    continue 'outer;
                }
            }
        }
        return items;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use Value::*;

    fn id_closure() -> Value {
        Value::Closure(super::Closure {
            body: crate::lang::NodeId(0),
            env: vec![],
        })
    }

    #[test]
    fn react_is_commutative() {
        let vals = [
            Num(2),
            Add(3),
            Add(-1),
            Value::bag(vec![Num(1)]),
            id_closure(),
        ];
        for a in &vals {
            for b in &vals {
                assert_eq!(react(a, b), react(b, a), "{a} vs {b}");
            }
        }
    }

    fn v(x: Value) -> Settled {
        Settled::Value(x)
    }

    #[test]
    fn spec_examples() {
        assert_eq!(settle(vec![]), v(Value::bag(vec![])));
        assert_eq!(settle(vec![Add(1)]), v(Add(1)));
        assert_eq!(settle(vec![Add(1), Add(1), Add(1)]), v(Add(3)));
        assert_eq!(settle(vec![Num(5), Add(1), Add(1)]), v(Num(7)));
        assert_eq!(settle(vec![Add(1), Add(2)]), v(Add(3)));
        assert_eq!(
            settle(vec![Add(1), Num(1), Num(2)]),
            v(Value::bag(vec![Add(1), Num(1), Num(2)]))
        );
    }

    #[test]
    fn closures() {
        let c = id_closure();
        let Value::Closure(cl) = c.clone() else {
            unreachable!()
        };
        // A closure alone is a value.
        assert_eq!(settle(vec![c.clone()]), v(c.clone()));
        // A closure and a datum is an application, the datum may be a bag.
        assert_eq!(
            settle(vec![Num(5), c.clone()]),
            Settled::Apply {
                closure: cl.clone(),
                arg: Num(5)
            }
        );
        let bag = Value::bag(vec![Num(1), Num(2)]);
        assert_eq!(
            settle(vec![bag.clone(), c.clone()]),
            Settled::Apply {
                closure: cl,
                arg: bag
            }
        );
        // Two closures, or a closure and an Add, do not react.
        assert_eq!(
            settle(vec![c.clone(), c.clone()]),
            v(Value::bag(vec![c.clone(), c.clone()]))
        );
        assert_eq!(
            settle(vec![c.clone(), Add(1)]),
            v(Value::bag(vec![Add(1), c.clone()]))
        );
        // A closure with two data is stuck.
        assert_eq!(
            settle(vec![c.clone(), Num(1), Num(2)]),
            v(Value::bag(vec![Num(1), Num(2), c]))
        );
    }

    #[test]
    fn settle_is_order_independent() {
        // Every permutation of a small mixed bag settles identically.
        let base = vec![
            Add(1),
            Num(4),
            Add(2),
            Value::bag(vec![Num(0)]),
            Add(-3),
            id_closure(),
        ];
        let expected = settle(base.clone());
        for p in permutations(&base) {
            assert_eq!(settle(p), expected);
        }
    }

    fn permutations(v: &[Value]) -> Vec<Vec<Value>> {
        if v.len() <= 1 {
            return vec![v.to_vec()];
        }
        let mut out = Vec::new();
        for i in 0..v.len() {
            let mut rest = v.to_vec();
            let x = rest.remove(i);
            for mut p in permutations(&rest) {
                p.insert(0, x.clone());
                out.push(p);
            }
        }
        out
    }
}
