//! A CEK machine: explicit control, environment, and a stack of frames.
//!
//! The control is either *evaluate this node in this environment* or *return
//! this value*; the stack holds one frame per panel (or applied binder) whose
//! children are still being evaluated. One `step` is one transition. The
//! stack is exactly what the page will show as evaluation runs, which is why
//! this machine exists alongside the walker.

use std::collections::{BTreeMap, HashMap};

use crate::lang::chemistry::{settle, Settled};
use crate::lang::machine::{LoadError, Machine, MachineView, Progress, RunError};
use crate::lang::term::{Node, NodeId, Program};
use crate::lang::value::{Closure, Value};

#[derive(Clone, Debug)]
enum Control {
    Eval(NodeId, Vec<Value>),
    Return(Value),
}

#[derive(Clone, Debug)]
struct Frame {
    /// The panel or binder being assembled.
    node: NodeId,
    /// The environment its children see.
    env: Vec<Value>,
    /// Children not yet evaluated, last first (so `pop` gives the next).
    todo: Vec<NodeId>,
    /// Values of the children evaluated so far.
    done: Vec<Value>,
}

#[derive(Debug, Default)]
pub struct Cek {
    program: Option<Program>,
    root: Option<NodeId>,
    free: HashMap<NodeId, u32>,
    control: Option<Control>,
    stack: Vec<Frame>,
    settled: BTreeMap<NodeId, Value>,
    steps: u64,
    finished: bool,
}

impl Cek {
    fn closed(&self, id: NodeId) -> bool {
        self.free.get(&id).copied().unwrap_or(0) == 0
    }

    /// Record a value for a node if the node is closed (SPEC §4).
    fn remember(&mut self, id: NodeId, v: &Value) {
        if self.closed(id) {
            self.settled.insert(id, v.clone());
        }
    }

    /// Start evaluating `node`'s children under `env`; returns the next
    /// control. An empty body settles immediately.
    fn open(&mut self, node: NodeId, env: Vec<Value>) -> Control {
        let program = self.program.as_ref().expect("loaded");
        let mut todo: Vec<NodeId> = program.children(node).to_vec();
        todo.reverse();
        match todo.pop() {
            Some(first) => {
                self.stack.push(Frame {
                    node,
                    env: env.clone(),
                    todo,
                    done: Vec::new(),
                });
                Control::Eval(first, env)
            }
            None => self.close(node, Vec::new()),
        }
    }

    /// A frame's children are all evaluated: settle them. The result is
    /// either the frame's value, or an application whose result will be.
    fn close(&mut self, node: NodeId, done: Vec<Value>) -> Control {
        match settle(done) {
            Settled::Value(v) => {
                self.remember(node, &v);
                Control::Return(v)
            }
            Settled::Apply { closure, arg } => {
                // The applied binder's body is evaluated in the place of
                // `node`: push a frame for it that reports `node` as the
                // panel being assembled, so the value lands in the right spot.
                let env = closure.extended(arg);
                let program = self.program.as_ref().expect("loaded");
                let mut todo: Vec<NodeId> = program.children(closure.body).to_vec();
                todo.reverse();
                match todo.pop() {
                    Some(first) => {
                        self.stack.push(Frame {
                            node,
                            env: env.clone(),
                            todo,
                            done: Vec::new(),
                        });
                        Control::Eval(first, env)
                    }
                    None => self.close(node, Vec::new()),
                }
            }
        }
    }
}

impl Machine for Cek {
    fn load(&mut self, program: &Program, root: NodeId) -> Result<(), LoadError> {
        Self::validate(program, root)?;
        self.free = program.free_depths(root);
        self.program = Some(program.clone());
        self.root = Some(root);
        self.control = Some(Control::Eval(root, Vec::new()));
        self.stack.clear();
        self.settled.clear();
        self.steps = 0;
        self.finished = false;
        Ok(())
    }

    fn step(&mut self) -> Progress {
        if self.program.is_none() {
            return Progress::Failed(RunError::NotLoaded);
        }
        if self.finished {
            return Progress::Done;
        }
        let Some(control) = self.control.take() else {
            return Progress::Failed(RunError::Internal("no control".into()));
        };
        self.steps += 1;

        let next = match control {
            Control::Eval(id, env) => {
                if let Some(v) = self.settled.get(&id) {
                    Control::Return(v.clone()) // shared closed node: reuse
                } else {
                    let node = self.program.as_ref().expect("loaded").get(id).cloned();
                    match node {
                        Some(Node::Panel(_)) => self.open(id, env),
                        Some(Node::Binder(_)) => {
                            let needed = self.free.get(&id).copied().unwrap_or(0);
                            let v = Value::Closure(Closure::capture(id, &env, needed));
                            self.remember(id, &v);
                            Control::Return(v)
                        }
                        Some(Node::Hole(d)) => match env.iter().rev().nth(d as usize) {
                            Some(v) => Control::Return(v.clone()),
                            None => {
                                return Progress::Failed(RunError::Internal(format!(
                                    "unbound hole {d} at {id}"
                                )))
                            }
                        },
                        Some(Node::Dot) => {
                            self.remember(id, &Value::Add(1));
                            Control::Return(Value::Add(1))
                        }
                        Some(Node::Num(n)) => {
                            self.remember(id, &Value::Num(n));
                            Control::Return(Value::Num(n))
                        }
                        None => {
                            return Progress::Failed(RunError::Internal(format!(
                                "missing node {id}"
                            )))
                        }
                    }
                }
            }
            Control::Return(v) => match self.stack.last_mut() {
                None => {
                    // The root has returned.
                    self.finished = true;
                    self.control = None;
                    return Progress::Done;
                }
                Some(frame) => {
                    frame.done.push(v);
                    match frame.todo.pop() {
                        Some(next) => Control::Eval(next, frame.env.clone()),
                        None => {
                            let frame = self.stack.pop().expect("frame");
                            self.close(frame.node, frame.done)
                        }
                    }
                }
            },
        };
        self.control = Some(next);
        Progress::Running
    }

    fn view(&self) -> MachineView {
        let mut pending: Vec<NodeId> = self.stack.iter().map(|f| f.node).collect();
        let focus = match (&self.control, self.stack.last()) {
            (Some(Control::Eval(id, _)), _) => Some(*id),
            (Some(Control::Return(_)), Some(frame)) => Some(frame.node),
            (Some(Control::Return(_)), None) => self.root,
            (None, _) => None,
        };
        match &self.control {
            Some(Control::Eval(id, _)) => pending.push(*id),
            // The root's value is in hand but not yet delivered: one step left.
            Some(Control::Return(_)) if self.stack.is_empty() => pending.extend(self.root),
            _ => {}
        }
        MachineView {
            focus,
            settled: self.settled.clone(),
            pending,
            steps: self.steps,
        }
    }

    fn result(&self) -> Option<&Value> {
        if self.finished {
            self.settled.get(&self.root?)
        } else {
            None
        }
    }
}

#[cfg(test)]
crate::conformance_tests!(super::Cek);
