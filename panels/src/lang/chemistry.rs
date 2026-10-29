//! Chemistry: what molecules do when they meet (SPEC §3.2–3.4).
//!
//! This module owns the *rules*. Machines own the *strategy* and must call
//! only [`react`] and [`settle`]; they never hard-code a reaction.

use super::value::Value;

/// The complete pairwise chemistry. Commutative by construction.
pub fn react(a: &Value, b: &Value) -> Option<Value> {
    use Value::*;
    match (a, b) {
        (Add(m), Add(n)) => Some(Add(m + n)),
        (Add(n), Num(x)) | (Num(x), Add(n)) => Some(Num(x + n)),
        _ => None,
    }
}

/// Turn the evaluated children of a panel into the panel's value.
///
/// 1. Coalesce transformers until no two react.
/// 2. If exactly one transformer and exactly one datum remain and they react,
///    apply.
/// 3. One molecule left ⇒ it is the value; otherwise the canonical `Bag`.
///
/// Order-independent for the v0 chemistry; see SPEC §3.4 for the obligation
/// this places on any extension.
pub fn settle(molecules: Vec<Value>) -> Value {
    let (mut transformers, mut data): (Vec<Value>, Vec<Value>) =
        molecules.into_iter().partition(Value::is_transformer);

    // 1. Coalesce transformers. Additive transformers always react, so this
    //    is a plain fold, but we go through `react` to keep the rule in one place.
    transformers = coalesce(transformers);

    // 2. Apply.
    if transformers.len() == 1 && data.len() == 1 {
        if let Some(v) = react(&transformers[0], &data[0]) {
            return v;
        }
    }

    // 3. Unwrap or bag.
    let mut rest = transformers;
    rest.append(&mut data);
    if rest.len() == 1 {
        rest.pop().unwrap()
    } else {
        Value::bag(rest)
    }
}

/// Repeatedly react any two members that react, until none do.
fn coalesce(mut items: Vec<Value>) -> Vec<Value> {
    'outer: loop {
        for i in 0..items.len() {
            for j in (i + 1)..items.len() {
                if let Some(v) = react(&items[i], &items[j]) {
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

    #[test]
    fn react_is_commutative() {
        let vals = [Num(2), Add(3), Add(-1), Value::bag(vec![Num(1)])];
        for a in &vals {
            for b in &vals {
                assert_eq!(react(a, b), react(b, a), "{a} vs {b}");
            }
        }
    }

    #[test]
    fn spec_examples() {
        assert_eq!(settle(vec![]), Value::bag(vec![]));
        assert_eq!(settle(vec![Add(1)]), Add(1));
        assert_eq!(settle(vec![Add(1), Add(1), Add(1)]), Add(3));
        assert_eq!(settle(vec![Num(5), Add(1), Add(1)]), Num(7));
        assert_eq!(settle(vec![Add(1), Add(2)]), Add(3));
        assert_eq!(
            settle(vec![Add(1), Num(1), Num(2)]),
            Value::bag(vec![Add(1), Num(1), Num(2)])
        );
    }

    #[test]
    fn settle_is_order_independent() {
        // Every permutation of a small mixed bag settles identically.
        let base = vec![Add(1), Num(4), Add(2), Value::bag(vec![Num(0)]), Add(-3)];
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
