//! The language core. Pure Rust, no browser, no pixels.
//!
//! Read `SPEC.md` first. In brief: a program is a tree of panels, each a
//! multiset of children; juxtaposition is commutative and nesting is ordered.
//! `term` is the program graph, `value` and `chemistry` are what things are and
//! what they do when they meet, `machine` is the contract an evaluator fulfils,
//! and `conformance` is the executable form of the spec.

pub mod chemistry;
pub mod conformance;
pub mod machine;
pub mod machines;
pub mod term;
pub mod value;

pub use machine::{LoadError, Machine, MachineView, Progress, RunError};
pub use machines::{Cek, Walker};
pub use term::{Node, NodeId, Program};
pub use value::Value;
