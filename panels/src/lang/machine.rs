//! The evaluation contract (SPEC §4). A `Machine` is a *strategy* for making
//! molecules meet; it must not contain chemistry.

use std::collections::BTreeMap;
use std::fmt;

use super::term::{NodeId, Program};
use super::value::Value;

/// Why a program could not be loaded.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum LoadError {
    /// `root` is not in the arena.
    NoSuchRoot(NodeId),
    /// Some panel's child is not in the arena: (panel, child).
    Dangling(NodeId, NodeId),
    /// The graph reachable from `root` contains a cycle through this node.
    Cycle(NodeId),
}

impl fmt::Display for LoadError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            LoadError::NoSuchRoot(n) => write!(f, "root {n} does not exist"),
            LoadError::Dangling(p, c) => write!(f, "panel {p} refers to missing node {c}"),
            LoadError::Cycle(n) => write!(f, "cycle through {n}"),
        }
    }
}

/// Why a loaded program could not finish.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum RunError {
    /// `step` was called before a successful `load`.
    NotLoaded,
    /// A machine-specific failure; must not occur for any valid v0 program.
    Internal(String),
}

impl fmt::Display for RunError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            RunError::NotLoaded => write!(f, "no program loaded"),
            RunError::Internal(s) => write!(f, "internal: {s}"),
        }
    }
}

/// The outcome of a `step` or `run`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Progress {
    /// Work remains.
    Running,
    /// The root has settled; `result()` is `Some`.
    Done,
    /// Evaluation cannot continue.
    Failed(RunError),
}

/// Everything the UI is allowed to know about a machine's state.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct MachineView {
    /// The node the machine is currently working on, if any.
    pub focus: Option<NodeId>,
    /// Nodes whose value is known, with that value (canonical).
    pub settled: BTreeMap<NodeId, Value>,
    /// Pending work, outermost first. Semantics are machine-defined but it
    /// must be non-empty while `Running` and empty once `Done`.
    pub pending: Vec<NodeId>,
    /// Number of `step`s taken since `load`.
    pub steps: u64,
}

pub trait Machine {
    /// Validate and reset. Must reject cycles and dangling ids (SPEC §5).
    fn load(&mut self, program: &Program, root: NodeId) -> Result<(), LoadError>;

    /// Exactly one unit of work. Idempotent after `Done` / `Failed`.
    fn step(&mut self) -> Progress;

    /// The machine's state as the UI may see it.
    fn view(&self) -> MachineView;

    /// `Some` iff the last `Progress` was `Done`.
    fn result(&self) -> Option<&Value>;

    /// Step at most `fuel` times, stopping early on `Done` / `Failed`.
    fn run(&mut self, fuel: u64) -> Progress {
        let mut last = Progress::Running;
        for _ in 0..fuel {
            last = self.step();
            if last != Progress::Running {
                break;
            }
        }
        last
    }

    /// Shared validation every machine should call at the top of `load`.
    fn validate(program: &Program, root: NodeId) -> Result<(), LoadError>
    where
        Self: Sized,
    {
        if program.get(root).is_none() {
            return Err(LoadError::NoSuchRoot(root));
        }
        if let Some((p, c)) = program.dangling() {
            return Err(LoadError::Dangling(p, c));
        }
        if let Some(n) = program.find_cycle(root) {
            return Err(LoadError::Cycle(n));
        }
        Ok(())
    }
}
