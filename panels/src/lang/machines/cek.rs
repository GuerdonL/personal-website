//! A CEK-style machine: explicit control and an explicit stack of frames.
//!
//! The control is either *evaluate this node* or *return this value*; the
//! stack holds one frame per panel whose children are still being evaluated.
//! One `step` is one transition. The stack is exactly what the page will show
//! as evaluation runs, which is why this machine exists alongside the walker.
//!
//! No environment component yet: v0 has no binders (SPEC §2.1). When it does,
//! the E of CEK goes in the frame.

use std::collections::BTreeMap;

use crate::lang::chemistry::settle;
use crate::lang::machine::{LoadError, Machine, MachineView, Progress, RunError};
use crate::lang::term::{Node, NodeId, Program};
use crate::lang::value::Value;

#[derive(Clone, Debug)]
enum Control {
    Eval(NodeId),
    Return(Value),
}

#[derive(Clone, Debug)]
struct Frame {
    /// The panel being assembled.
    node: NodeId,
    /// Children not yet evaluated, last first (so `pop` gives the next).
    todo: Vec<NodeId>,
    /// Values of the children evaluated so far.
    done: Vec<Value>,
}

#[derive(Debug, Default)]
pub struct Cek {
    program: Option<Program>,
    root: Option<NodeId>,
    control: Option<Control>,
    stack: Vec<Frame>,
    settled: BTreeMap<NodeId, Value>,
    steps: u64,
    finished: bool,
}

impl Cek {
    fn leaf_value(node: &Node) -> Option<Value> {
        match node {
            Node::Dot => Some(Value::Add(1)),
            Node::Num(n) => Some(Value::Num(*n)),
            Node::Panel(_) => None,
        }
    }
}

impl Machine for Cek {
    fn load(&mut self, program: &Program, root: NodeId) -> Result<(), LoadError> {
        Self::validate(program, root)?;
        self.program = Some(program.clone());
        self.root = Some(root);
        self.control = Some(Control::Eval(root));
        self.stack.clear();
        self.settled.clear();
        self.steps = 0;
        self.finished = false;
        Ok(())
    }

    fn step(&mut self) -> Progress {
        let Some(program) = &self.program else {
            return Progress::Failed(RunError::NotLoaded);
        };
        if self.finished {
            return Progress::Done;
        }
        let Some(control) = self.control.take() else {
            return Progress::Failed(RunError::Internal("no control".into()));
        };
        self.steps += 1;

        let next = match control {
            Control::Eval(id) => {
                if let Some(v) = self.settled.get(&id) {
                    Control::Return(v.clone()) // shared node: reuse
                } else {
                    match program.get(id) {
                        Some(Node::Panel(kids)) => {
                            let mut todo: Vec<NodeId> = kids.clone();
                            todo.reverse();
                            match todo.pop() {
                                Some(first) => {
                                    self.stack.push(Frame {
                                        node: id,
                                        todo,
                                        done: Vec::new(),
                                    });
                                    Control::Eval(first)
                                }
                                None => {
                                    let v = settle(Vec::new());
                                    self.settled.insert(id, v.clone());
                                    Control::Return(v)
                                }
                            }
                        }
                        Some(leaf) => {
                            let v = Self::leaf_value(leaf).expect("leaf");
                            self.settled.insert(id, v.clone());
                            Control::Return(v)
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
                        Some(next) => Control::Eval(next),
                        None => {
                            let frame = self.stack.pop().expect("frame");
                            let v = settle(frame.done);
                            self.settled.insert(frame.node, v.clone());
                            Control::Return(v)
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
            (Some(Control::Eval(id)), _) => Some(*id),
            (Some(Control::Return(_)), Some(frame)) => Some(frame.node),
            (Some(Control::Return(_)), None) => self.root,
            (None, _) => None,
        };
        match &self.control {
            Some(Control::Eval(id)) => pending.push(*id),
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
