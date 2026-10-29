//! Terms: the program graph (SPEC §2).

use std::collections::{HashMap, HashSet};
use std::fmt;

/// Index into a [`Program`]'s arena.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct NodeId(pub u32);

impl fmt::Display for NodeId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "#{}", self.0)
    }
}

/// One node of the program graph.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Node {
    /// A membrane holding a multiset of children. The `Vec` order is **not**
    /// observable (SPEC §1); use [`Program::children`] and treat it as a bag.
    Panel(Vec<NodeId>),
    /// A membrane with a port: a function of one argument (SPEC §2). Its
    /// children are evaluated only when it meets an argument.
    Binder(Vec<NodeId>),
    /// A use of a bound value: the `depth`-th enclosing binder, innermost
    /// first (a de Bruijn index).
    Hole(u32),
    /// The additive unit: the curried function `+1`.
    Dot,
    /// A numeral literal (sugar for a right-nested chain of digits; SPEC §6.1).
    Num(i64),
}

/// An arena of nodes forming a DAG. Sharing is expressed by a `NodeId`
/// appearing as the child of more than one panel.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Program {
    nodes: Vec<Node>,
}

impl Program {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn len(&self) -> usize {
        self.nodes.len()
    }

    pub fn is_empty(&self) -> bool {
        self.nodes.is_empty()
    }

    pub fn push(&mut self, node: Node) -> NodeId {
        let id = NodeId(self.nodes.len() as u32);
        self.nodes.push(node);
        id
    }

    pub fn dot(&mut self) -> NodeId {
        self.push(Node::Dot)
    }

    pub fn num(&mut self, n: i64) -> NodeId {
        self.push(Node::Num(n))
    }

    pub fn panel(&mut self, children: impl IntoIterator<Item = NodeId>) -> NodeId {
        self.push(Node::Panel(children.into_iter().collect()))
    }

    pub fn binder(&mut self, children: impl IntoIterator<Item = NodeId>) -> NodeId {
        self.push(Node::Binder(children.into_iter().collect()))
    }

    pub fn hole(&mut self, depth: u32) -> NodeId {
        self.push(Node::Hole(depth))
    }

    /// Convenience: a panel of `n` dots.
    pub fn dots(&mut self, n: usize) -> NodeId {
        let kids: Vec<NodeId> = (0..n).map(|_| self.dot()).collect();
        self.panel(kids)
    }

    pub fn get(&self, id: NodeId) -> Option<&Node> {
        self.nodes.get(id.0 as usize)
    }

    pub fn get_mut(&mut self, id: NodeId) -> Option<&mut Node> {
        self.nodes.get_mut(id.0 as usize)
    }

    /// The children of a panel or binder as a bag; empty for leaves.
    pub fn children(&self, id: NodeId) -> &[NodeId] {
        match self.get(id) {
            Some(Node::Panel(kids)) | Some(Node::Binder(kids)) => kids,
            _ => &[],
        }
    }

    /// How many enclosing binders a node needs: 0 means the node is
    /// **closed** and has a value independent of context (SPEC §2).
    /// Path-independent, so it is well defined on a DAG. Panics on cycles;
    /// call [`Program::find_cycle`] first.
    pub fn free_depth(&self, id: NodeId) -> u32 {
        let mut memo: HashMap<NodeId, u32> = HashMap::new();
        self.free_depth_memo(id, &mut memo)
    }

    fn free_depth_memo(&self, id: NodeId, memo: &mut HashMap<NodeId, u32>) -> u32 {
        if let Some(&d) = memo.get(&id) {
            return d;
        }
        let d = match self.get(id) {
            Some(Node::Hole(d)) => d + 1,
            Some(Node::Panel(kids)) => kids
                .iter()
                .map(|&k| self.free_depth_memo(k, memo))
                .max()
                .unwrap_or(0),
            Some(Node::Binder(kids)) => kids
                .iter()
                .map(|&k| self.free_depth_memo(k, memo))
                .max()
                .unwrap_or(0)
                .saturating_sub(1),
            _ => 0,
        };
        memo.insert(id, d);
        d
    }

    /// `free_depth` for every node reachable from `root`, in one pass.
    pub fn free_depths(&self, root: NodeId) -> HashMap<NodeId, u32> {
        let mut memo = HashMap::new();
        for id in self.reachable(root) {
            self.free_depth_memo(id, &mut memo);
        }
        memo
    }

    pub fn ids(&self) -> impl Iterator<Item = NodeId> {
        (0..self.nodes.len() as u32).map(NodeId)
    }

    /// Every child id of every panel refers to a node in the arena.
    pub fn is_closed(&self) -> bool {
        self.dangling().is_none()
    }

    /// The first (panel, child) pair whose child is not in the arena, if any.
    pub fn dangling(&self) -> Option<(NodeId, NodeId)> {
        for id in self.ids() {
            for &c in self.children(id) {
                if self.get(c).is_none() {
                    return Some((id, c));
                }
            }
        }
        None
    }

    /// Is `root` part of, or above, a cycle? Returns a node on the cycle if so.
    pub fn find_cycle(&self, root: NodeId) -> Option<NodeId> {
        #[derive(Clone, Copy, PartialEq)]
        enum Mark {
            Open,
            Closed,
        }
        let mut mark: Vec<Option<Mark>> = vec![None; self.nodes.len()];
        // Iterative DFS with an explicit stack of (node, next-child-index).
        let mut stack: Vec<(NodeId, usize)> = Vec::new();
        self.get(root)?;
        mark[root.0 as usize] = Some(Mark::Open);
        stack.push((root, 0));
        while let Some(&mut (id, ref mut i)) = stack.last_mut() {
            let kids = self.children(id);
            if *i < kids.len() {
                let c = kids[*i];
                *i += 1;
                match mark.get(c.0 as usize).copied().flatten() {
                    Some(Mark::Open) => return Some(c),
                    Some(Mark::Closed) => {}
                    None => {
                        if self.get(c).is_some() {
                            mark[c.0 as usize] = Some(Mark::Open);
                            stack.push((c, 0));
                        }
                    }
                }
            } else {
                mark[id.0 as usize] = Some(Mark::Closed);
                stack.pop();
            }
        }
        None
    }

    /// Nodes reachable from `root`, including `root`, in no particular order.
    pub fn reachable(&self, root: NodeId) -> HashSet<NodeId> {
        let mut seen = HashSet::new();
        let mut todo = vec![root];
        while let Some(id) = todo.pop() {
            if self.get(id).is_none() || !seen.insert(id) {
                continue;
            }
            todo.extend(self.children(id).iter().copied());
        }
        seen
    }

    /// A copy of the program with every panel's children permuted by `perm`.
    /// Because sibling order is not meaning (SPEC §1), the result must evaluate
    /// identically; the conformance suite relies on this.
    pub fn shuffled(&self, mut perm: impl FnMut(&mut Vec<NodeId>)) -> Program {
        let mut p = self.clone();
        for node in &mut p.nodes {
            if let Node::Panel(kids) | Node::Binder(kids) = node {
                perm(kids);
            }
        }
        p
    }
}
