//! The language core. Pure Rust, no browser, no pixels.
//!
//! Read `SPEC.md` first. In brief: a program is a tree of panels, each a
//! multiset of children; juxtaposition is commutative and nesting is ordered.
//! `term` is the program graph, `value` and `chemistry` are what things are and
//! what they do when they meet, `machine` is the contract an evaluator fulfils,
//! `conformance` is the executable form of the spec, and `text` is a
//! notation for writing programs down.

pub mod chemistry;
pub mod conformance;
pub mod machine;
pub mod machines;
pub mod term;
pub mod text;
pub mod value;

pub use chemistry::{Reaction, Settled};
pub use machine::{LoadError, Machine, MachineView, Progress, RunError};
pub use machines::{Cek, Walker};
pub use term::{Node, NodeId, Program};
pub use text::{parse, print};
pub use value::{Closure, Value};
