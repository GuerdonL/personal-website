//! Evaluators. Each is a *strategy* implementing [`super::Machine`] against
//! the same chemistry and the same conformance suite (SPEC §0.2, §4).
//!
//! - [`walker`] — bottom-up: settles reachable nodes in a precomputed
//!   post-order, one node per step. The trivial reading of SPEC §3.
//! - [`cek`] — top-down, demand-driven: an explicit control/stack machine
//!   whose stack is what the page will animate.

pub mod cek;
pub mod walker;

pub use cek::Cek;
pub use walker::Walker;

#[cfg(test)]
mod agreement {
    //! Two machines must agree on every program, not only the ones in the
    //! conformance suite. This generates a few hundred random DAGs and
    //! checks results, settled maps, and that both reject the same inputs.

    use super::{Cek, Walker};
    use crate::lang::conformance::FUEL;
    use crate::lang::{Machine, Node, NodeId, Program, Progress};

    struct Lcg(u64);
    impl Lcg {
        fn next(&mut self) -> u64 {
            self.0 = self
                .0
                .wrapping_mul(6364136223846793005)
                .wrapping_add(1442695040888963407);
            self.0 >> 33
        }
        fn below(&mut self, n: u64) -> u64 {
            self.next() % n.max(1)
        }
    }

    /// A random acyclic program: nodes only ever point at lower ids, so the
    /// last node is a root that reaches an arbitrary DAG with sharing.
    fn random_program(rng: &mut Lcg, size: usize) -> (Program, NodeId) {
        let mut p = Program::new();
        for i in 0..size {
            let node = match rng.below(10) {
                0..=3 => Node::Dot,
                4..=5 => Node::Num(rng.below(20) as i64 - 5),
                _ => {
                    let n = rng.below(4) as usize;
                    let kids = (0..n).map(|_| NodeId(rng.below(i as u64) as u32)).collect();
                    Node::Panel(if i == 0 { Vec::new() } else { kids })
                }
            };
            p.push(node);
        }
        let last = NodeId(size as u32 - 1);
        (p, last)
    }

    fn run<M: Machine + Default>(p: &Program, root: NodeId) -> Option<(crate::lang::Value, usize)> {
        let mut m = M::default();
        m.load(p, root).ok()?;
        assert_eq!(m.run(FUEL), Progress::Done);
        Some((m.result().unwrap().clone(), m.view().settled.len()))
    }

    #[test]
    fn walker_and_cek_agree_on_random_programs() {
        let mut rng = Lcg(42);
        for case in 0..400 {
            let size = 1 + rng.below(30) as usize;
            let (p, root) = random_program(&mut rng, size);
            let w = run::<Walker>(&p, root);
            let c = run::<Cek>(&p, root);
            assert_eq!(w, c, "case {case}: {p:?}");
        }
    }

    #[test]
    fn both_reject_the_same_programs() {
        let mut p = Program::new();
        let a = p.panel([]);
        let b = p.panel([a]);
        if let Some(Node::Panel(k)) = p.get_mut(a) {
            k.push(b);
        }
        let mut w = Walker::default();
        let mut c = Cek::default();
        assert_eq!(w.load(&p, a), c.load(&p, a));
        let mut q = Program::new();
        let r = q.panel([NodeId(7)]);
        assert_eq!(w.load(&q, r), c.load(&q, r));
    }
}
