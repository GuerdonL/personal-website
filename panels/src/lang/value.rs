//! Values (SPEC §3.1). Canonical: a `Bag` is always sorted, so `==` on values
//! is multiset equality.

use std::fmt;

use super::term::NodeId;

/// A binder together with the values of its enclosing binders, innermost
/// last (SPEC §3.1). Equality is structural.
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct Closure {
    pub body: NodeId,
    pub env: Vec<Value>,
}

impl Closure {
    /// Capture a binder. `env` is the full environment at the point of
    /// capture, innermost last; `needed` is the binder's free depth (how
    /// many enclosing binders its holes can reach). Only those are kept, so
    /// a closure is canonical: the same binder captured in different places
    /// with the same reachable values is the same value (SPEC §3.1).
    pub fn capture(body: NodeId, env: &[Value], needed: u32) -> Closure {
        let keep = (needed as usize).min(env.len());
        Closure {
            body,
            env: env[env.len() - keep..].to_vec(),
        }
    }

    /// The environment the binder's children see once `arg` has arrived.
    pub fn extended(&self, arg: Value) -> Vec<Value> {
        let mut env = self.env.clone();
        env.push(arg);
        env
    }
}

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum Value {
    /// A datum.
    Num(i64),
    /// A transformer: the function `x ↦ x + n`.
    Add(i64),
    /// A transformer: a binder waiting for its argument.
    Closure(Closure),
    /// A settled multiset that would not react further. Always sorted;
    /// construct only through [`Value::bag`].
    Bag(Vec<Value>),
}

impl Value {
    /// The only way to make a `Bag`: sorts into canonical order.
    pub fn bag(mut items: Vec<Value>) -> Value {
        items.sort();
        Value::Bag(items)
    }

    pub fn is_transformer(&self) -> bool {
        matches!(self, Value::Add(_) | Value::Closure(_))
    }

    pub fn is_datum(&self) -> bool {
        !self.is_transformer()
    }

    /// True iff every `Bag` inside is sorted. Machines must only ever
    /// produce canonical values; the conformance suite checks this.
    pub fn is_canonical(&self) -> bool {
        match self {
            Value::Bag(items) => {
                items.windows(2).all(|w| w[0] <= w[1]) && items.iter().all(Value::is_canonical)
            }
            Value::Closure(c) => c.env.iter().all(Value::is_canonical),
            _ => true,
        }
    }
}

impl fmt::Display for Value {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Value::Num(n) => write!(f, "{n}"),
            Value::Add(n) => write!(f, "+{n}"),
            Value::Closure(c) => {
                write!(f, "λ{}", c.body)?;
                if !c.env.is_empty() {
                    write!(f, "[")?;
                    for (i, v) in c.env.iter().enumerate() {
                        if i > 0 {
                            write!(f, " ")?;
                        }
                        write!(f, "{v}")?;
                    }
                    write!(f, "]")?;
                }
                Ok(())
            }
            Value::Bag(items) => {
                write!(f, "{{")?;
                for (i, v) in items.iter().enumerate() {
                    if i > 0 {
                        write!(f, " ")?;
                    }
                    write!(f, "{v}")?;
                }
                write!(f, "}}")
            }
        }
    }
}
