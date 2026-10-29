//! Values (SPEC §3.1). Canonical: a `Bag` is always sorted, so `==` on values
//! is multiset equality.

use std::fmt;

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum Value {
    /// A datum.
    Num(i64),
    /// A transformer: the function `x ↦ x + n`.
    Add(i64),
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
        matches!(self, Value::Add(_))
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
            _ => true,
        }
    }
}

impl fmt::Display for Value {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Value::Num(n) => write!(f, "{n}"),
            Value::Add(n) => write!(f, "+{n}"),
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
