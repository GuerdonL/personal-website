//! Bottom-up evaluation in a precomputed post-order.
//!
//! `load` lists every **closed** node reachable from the root with children
//! before parents; each `step` settles the next one. A closed node's closed
//! children are already settled and are looked up; its open children (binder
//! bodies with holes) are evaluated on the spot, recursively, under an
//! environment. A shared node is settled once. This is the simplest strategy
//! that honours the contract, and it is deliberately unlike [`super::Cek`]:
//! no stack, no demand, nothing to animate.

use std::collections::{BTreeMap, HashMap, HashSet};

use crate::lang::chemistry::{settle, Settled};
use crate::lang::machine::{LoadError, Machine, MachineView, Progress, RunError};
use crate::lang::term::{Node, NodeId, Program};
use crate::lang::value::{Closure, Value};

#[derive(Debug, Default)]
pub struct Walker {
    program: Option<Program>,
    root: Option<NodeId>,
    free: HashMap<NodeId, u32>,
    order: Vec<NodeId>,
    next: usize,
    settled: BTreeMap<NodeId, Value>,
    steps: u64,
}

impl Walker {
    /// Post-order over every node reachable from `root`, emitting only the
    /// closed ones. Open nodes are walked through — a closed node inside a
    /// binder body still has a value of its own — but never listed.
    fn post_order(program: &Program, root: NodeId, free: &HashMap<NodeId, u32>) -> Vec<NodeId> {
        let mut out = Vec::new();
        let mut done: HashSet<NodeId> = HashSet::new();
        let mut stack: Vec<(NodeId, usize)> = vec![(root, 0)];
        let mut open: HashSet<NodeId> = HashSet::from([root]);
        while let Some(&mut (id, ref mut i)) = stack.last_mut() {
            let kids = program.children(id);
            if *i < kids.len() {
                let c = kids[*i];
                *i += 1;
                if !done.contains(&c) && open.insert(c) {
                    stack.push((c, 0));
                }
            } else {
                stack.pop();
                open.remove(&id);
                done.insert(id);
                if free.get(&id).copied().unwrap_or(0) == 0 {
                    out.push(id);
                }
            }
        }
        out
    }

    fn status(&self) -> Progress {
        if self.program.is_none() {
            Progress::Failed(RunError::NotLoaded)
        } else if self.next >= self.order.len() {
            Progress::Done
        } else {
            Progress::Running
        }
    }

    /// Evaluate `id` under `env` (innermost binder last). Closed nodes come
    /// from the memo when present; everything else is computed here.
    fn eval(&self, id: NodeId, env: &[Value]) -> Result<Value, RunError> {
        if let Some(v) = self.settled.get(&id) {
            return Ok(v.clone());
        }
        let program = self.program.as_ref().ok_or(RunError::NotLoaded)?;
        match program.get(id) {
            Some(Node::Dot) => Ok(Value::Add(1)),
            Some(Node::Num(n)) => Ok(Value::Num(*n)),
            Some(Node::Hole(d)) => env
                .iter()
                .rev()
                .nth(*d as usize)
                .cloned()
                .ok_or_else(|| RunError::Internal(format!("unbound hole {d} at {id}"))),
            Some(Node::Binder(_)) => Ok(Value::Closure(Closure::capture(
                id,
                env,
                self.free.get(&id).copied().unwrap_or(0),
            ))),
            Some(Node::Panel(kids)) => {
                let vals = kids
                    .iter()
                    .map(|&k| self.eval(k, env))
                    .collect::<Result<Vec<_>, _>>()?;
                self.finish(settle(vals))
            }
            None => Err(RunError::Internal(format!("missing node {id}"))),
        }
    }

    /// Run whatever `settle` asked for, to a value.
    fn finish(&self, s: Settled) -> Result<Value, RunError> {
        match s {
            Settled::Value(v) => Ok(v),
            Settled::Apply { closure, arg } => {
                let env = closure.extended(arg);
                let program = self.program.as_ref().ok_or(RunError::NotLoaded)?;
                let vals = program
                    .children(closure.body)
                    .iter()
                    .map(|&k| self.eval(k, &env))
                    .collect::<Result<Vec<_>, _>>()?;
                self.finish(settle(vals))
            }
        }
    }
}

impl Machine for Walker {
    fn load(&mut self, program: &Program, root: NodeId) -> Result<(), LoadError> {
        Self::validate(program, root)?;
        self.free = program.free_depths(root);
        self.order = Self::post_order(program, root, &self.free);
        self.program = Some(program.clone());
        self.root = Some(root);
        self.next = 0;
        self.settled.clear();
        self.steps = 0;
        Ok(())
    }

    fn step(&mut self) -> Progress {
        if self.program.is_none() {
            return Progress::Failed(RunError::NotLoaded);
        }
        let Some(&id) = self.order.get(self.next) else {
            return Progress::Done;
        };
        self.steps += 1;
        match self.eval(id, &[]) {
            Ok(v) => {
                self.settled.insert(id, v);
            }
            Err(e) => return Progress::Failed(e),
        }
        self.next += 1;
        self.status()
    }

    fn view(&self) -> MachineView {
        MachineView {
            focus: self.order.get(self.next).copied(),
            settled: self.settled.clone(),
            pending: self.order[self.next.min(self.order.len())..].to_vec(),
            steps: self.steps,
        }
    }

    fn result(&self) -> Option<&Value> {
        if self.status() == Progress::Done {
            self.settled.get(&self.root?)
        } else {
            None
        }
    }
}

#[cfg(test)]
crate::conformance_tests!(super::Walker);
