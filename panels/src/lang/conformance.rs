//! The executable spec (SPEC §5). Generic over any [`Machine`]; instantiate
//! per implementation with `conformance_tests!(MyMachine);` in that
//! implementation's test module.
//!
//! Every case is a plain function so it can also be run outside the test
//! harness (for example from the page, against a machine compiled to wasm).

use super::chemistry;
use super::machine::{LoadError, Machine, Progress};
use super::term::{NodeId, Program};
use super::value::Value;

/// Generous bound: no v0 machine needs anywhere near this many steps for the
/// programs in this file.
pub const FUEL: u64 = 100_000;

/// Load, run to completion, return the result. Panics with a useful message
/// if the machine misbehaves along the way.
pub fn eval<M: Machine + Default>(program: &Program, root: NodeId) -> Value {
    let mut m = M::default();
    m.load(program, root).expect("load should succeed");
    match m.run(FUEL) {
        Progress::Done => {}
        other => panic!(
            "expected Done, got {other:?} after {} steps",
            m.view().steps
        ),
    }
    let v = m.result().expect("result after Done").clone();
    assert!(v.is_canonical(), "result not canonical: {v}");
    assert_eq!(
        m.view().settled.get(&root),
        Some(&v),
        "view().settled[root] must equal result()"
    );
    assert!(
        m.view().pending.is_empty(),
        "pending must be empty once Done"
    );
    v
}

// ───────────────────────── programs used by the cases ─────────────────────────

/// `{1 {0 {8}}}` — a right-nested list of numerals.
pub fn list_108(p: &mut Program) -> NodeId {
    let eight = p.num(8);
    let inner = p.panel([eight]);
    let zero = p.num(0);
    let mid = p.panel([zero, inner]);
    let one = p.num(1);
    p.panel([one, mid])
}

/// A moderately tangled program with sharing, used by the order and
/// determinism cases. Returns (root, expected).
pub fn tangled(p: &mut Program) -> (NodeId, Value) {
    let two = p.dots(2); // Add 2
    let three = p.dots(3); // Add 3
    let five = p.num(5);
    let a = p.panel([two, five]); // Num 7
    let b = p.panel([two, three, two]); // Add 7  (shared `two` twice)
    let c = p.panel([a, b]); // Num 14
    let d = list_108(p); // data
    let root = p.panel([c, d, three]); // {Num 14, Bag[...], Add 3} → Num 17 and the bag stay: 2 data ⇒ stuck
    let expected = Value::bag(vec![
        Value::Add(3),
        Value::Num(14),
        Value::bag(vec![
            Value::Num(1),
            Value::bag(vec![Value::Num(0), Value::Num(8)]),
        ]),
    ]);
    (root, expected)
}

// ───────────────────────────────── settling ─────────────────────────────────

pub fn empty_panel<M: Machine + Default>() {
    let mut p = Program::new();
    let root = p.panel([]);
    assert_eq!(eval::<M>(&p, root), Value::bag(vec![]));
}

pub fn one_dot<M: Machine + Default>() {
    let mut p = Program::new();
    let root = p.dots(1);
    assert_eq!(eval::<M>(&p, root), Value::Add(1));
}

pub fn bare_dot_root<M: Machine + Default>() {
    // The root may be a leaf.
    let mut p = Program::new();
    let root = p.dot();
    assert_eq!(eval::<M>(&p, root), Value::Add(1));
}

pub fn three_dots<M: Machine + Default>() {
    let mut p = Program::new();
    let root = p.dots(3);
    assert_eq!(eval::<M>(&p, root), Value::Add(3));
}

pub fn numeral<M: Machine + Default>() {
    let mut p = Program::new();
    let n = p.num(5);
    let root = p.panel([n]);
    assert_eq!(eval::<M>(&p, root), Value::Num(5));
}

pub fn dots_apply_to_numeral<M: Machine + Default>() {
    let mut p = Program::new();
    let five = p.num(5);
    let d1 = p.dot();
    let d2 = p.dot();
    let root = p.panel([five, d1, d2]);
    assert_eq!(eval::<M>(&p, root), Value::Num(7));
}

pub fn nested_dots_coalesce<M: Machine + Default>() {
    let mut p = Program::new();
    let inner = p.dots(2);
    let d = p.dot();
    let root = p.panel([d, inner]);
    assert_eq!(eval::<M>(&p, root), Value::Add(3));
}

pub fn nesting_is_preserved<M: Machine + Default>() {
    let mut p = Program::new();
    let root = list_108(&mut p);
    assert_eq!(
        eval::<M>(&p, root),
        Value::bag(vec![
            Value::Num(1),
            Value::bag(vec![Value::Num(0), Value::Num(8)]),
        ])
    );
}

pub fn ambiguous_application_is_stuck<M: Machine + Default>() {
    let mut p = Program::new();
    let d = p.dot();
    let one = p.num(1);
    let two = p.num(2);
    let root = p.panel([d, one, two]);
    assert_eq!(
        eval::<M>(&p, root),
        Value::bag(vec![Value::Add(1), Value::Num(1), Value::Num(2)])
    );
}

pub fn sibling_transformers_compose_additively<M: Machine + Default>() {
    // {•••} {••} as siblings is +5, not 6 (SPEC §3.3).
    let mut p = Program::new();
    let a = p.dots(3);
    let b = p.dots(2);
    let root = p.panel([a, b]);
    assert_eq!(eval::<M>(&p, root), Value::Add(5));
}

pub fn machine_agrees_with_chemistry<M: Machine + Default>() {
    // Whatever a machine does, the root's value must equal settling the
    // children's values directly: strategy may not change rules.
    let mut p = Program::new();
    let (root, _) = tangled(&mut p);
    let mut m = M::default();
    m.load(&p, root).unwrap();
    assert_eq!(m.run(FUEL), Progress::Done);
    let view = m.view();
    let kids: Vec<Value> = p
        .children(root)
        .iter()
        .map(|c| view.settled.get(c).expect("every child settled").clone())
        .collect();
    assert_eq!(m.result(), Some(&chemistry::settle(kids)));
}

// ───────────────────────────────── sharing ──────────────────────────────────

pub fn shared_node_counts_each_time<M: Machine + Default>() {
    let mut p = Program::new();
    let two = p.dots(2);
    let root = p.panel([two, two]);
    assert_eq!(eval::<M>(&p, root), Value::Add(4));
}

pub fn shared_node_settled_once_in_view<M: Machine + Default>() {
    let mut p = Program::new();
    let two = p.dots(2);
    let root = p.panel([two, two]);
    let mut m = M::default();
    m.load(&p, root).unwrap();
    assert_eq!(m.run(FUEL), Progress::Done);
    assert_eq!(m.view().settled.get(&two), Some(&Value::Add(2)));
}

// ──────────────────────────── order independence ────────────────────────────

pub fn sibling_order_is_not_meaning<M: Machine + Default>() {
    let mut p = Program::new();
    let (root, expected) = tangled(&mut p);
    assert_eq!(eval::<M>(&p, root), expected);
    // A handful of deterministic permutations: reverse, rotate, and a
    // simple LCG-driven shuffle so no hidden order survives.
    let reversed = p.shuffled(|k| k.reverse());
    assert_eq!(eval::<M>(&reversed, root), expected, "reversed");
    let rotated = p.shuffled(|k| {
        if !k.is_empty() {
            k.rotate_left(1)
        }
    });
    assert_eq!(eval::<M>(&rotated, root), expected, "rotated");
    let mut seed: u64 = 0x9E37_79B9_7F4A_7C15;
    for round in 0..8 {
        let shuffled = p.shuffled(|k| {
            for i in (1..k.len()).rev() {
                seed = seed
                    .wrapping_mul(6364136223846793005)
                    .wrapping_add(1442695040888963407);
                let j = (seed >> 33) as usize % (i + 1);
                k.swap(i, j);
            }
        });
        assert_eq!(
            eval::<M>(&shuffled, root),
            expected,
            "shuffle round {round}"
        );
    }
}

// ──────────────────────────────── stepping ──────────────────────────────────

pub fn steps_until_done<M: Machine + Default>() {
    let mut p = Program::new();
    let (root, expected) = tangled(&mut p);
    let mut m = M::default();
    m.load(&p, root).unwrap();
    assert_eq!(m.result(), None, "no result before stepping");
    let mut n = 0u64;
    loop {
        match m.step() {
            Progress::Running => {
                n += 1;
                assert!(n < FUEL, "did not finish within FUEL steps");
                let v = m.view();
                assert!(v.focus.is_some(), "focus must be Some while Running");
                assert!(
                    !v.pending.is_empty(),
                    "pending must be non-empty while Running"
                );
                assert_eq!(m.result(), None, "no result while Running");
            }
            Progress::Done => break,
            Progress::Failed(e) => panic!("failed: {e}"),
        }
    }
    assert_eq!(m.result(), Some(&expected));
    assert!(m.view().steps >= n, "steps counter must count steps");
    // Idempotent after Done.
    assert_eq!(m.step(), Progress::Done);
    assert_eq!(m.result(), Some(&expected));
}

pub fn run_with_fuel_is_resumable<M: Machine + Default>() {
    let mut p = Program::new();
    let (root, expected) = tangled(&mut p);
    // Count the steps once.
    let mut probe = M::default();
    probe.load(&p, root).unwrap();
    assert_eq!(probe.run(FUEL), Progress::Done);
    let total = probe.view().steps;
    assert!(
        total >= 2,
        "a tangled program should take at least two steps"
    );
    // Then run it in two unequal halves.
    let mut m = M::default();
    m.load(&p, root).unwrap();
    assert_eq!(m.run(total / 2), Progress::Running);
    assert_eq!(m.result(), None);
    assert_eq!(m.run(FUEL), Progress::Done);
    assert_eq!(m.result(), Some(&expected));
}

pub fn step_before_load_fails<M: Machine + Default>() {
    let mut m = M::default();
    assert!(matches!(m.step(), Progress::Failed(_)));
    assert_eq!(m.result(), None);
}

// ─────────────────────────────── determinism ────────────────────────────────

pub fn deterministic<M: Machine + Default>() {
    let mut p = Program::new();
    let (root, _) = tangled(&mut p);
    let run = || {
        let mut m = M::default();
        m.load(&p, root).unwrap();
        assert_eq!(m.run(FUEL), Progress::Done);
        (m.result().unwrap().clone(), m.view().steps)
    };
    assert_eq!(run(), run());
}

pub fn reload_resets<M: Machine + Default>() {
    let mut p = Program::new();
    let a = p.dots(3);
    let b = p.dots(1);
    let mut m = M::default();
    m.load(&p, a).unwrap();
    assert_eq!(m.run(FUEL), Progress::Done);
    m.load(&p, b).unwrap();
    assert_eq!(m.result(), None, "load must reset");
    assert_eq!(m.view().steps, 0, "load must reset the step counter");
    assert_eq!(m.run(FUEL), Progress::Done);
    assert_eq!(m.result(), Some(&Value::Add(1)));
}

// ──────────────────────────────── rejection ─────────────────────────────────

pub fn rejects_cycle<M: Machine + Default>() {
    let mut p = Program::new();
    let a = p.panel([]);
    let b = p.panel([a]);
    // close the loop: a → b
    if let Some(super::term::Node::Panel(kids)) = p.get_mut(a) {
        kids.push(b);
    }
    let mut m = M::default();
    assert!(matches!(m.load(&p, a), Err(LoadError::Cycle(_))));
}

pub fn rejects_self_loop<M: Machine + Default>() {
    let mut p = Program::new();
    let a = p.panel([]);
    if let Some(super::term::Node::Panel(kids)) = p.get_mut(a) {
        kids.push(a);
    }
    let mut m = M::default();
    assert!(matches!(m.load(&p, a), Err(LoadError::Cycle(_))));
}

pub fn rejects_dangling<M: Machine + Default>() {
    let mut p = Program::new();
    let root = p.panel([NodeId(99)]);
    let mut m = M::default();
    assert!(matches!(m.load(&p, root), Err(LoadError::Dangling(_, _))));
}

pub fn rejects_missing_root<M: Machine + Default>() {
    let p = Program::new();
    let mut m = M::default();
    assert_eq!(m.load(&p, NodeId(0)), Err(LoadError::NoSuchRoot(NodeId(0))));
}

/// Instantiate the whole suite as `#[test]`s for one machine type.
#[macro_export]
macro_rules! conformance_tests {
    ($m:ty) => {
        mod conformance {
            use $crate::lang::conformance as c;
            macro_rules! case {
                ($name:ident) => {
                    #[test]
                    fn $name() {
                        c::$name::<$m>();
                    }
                };
            }
            // settling
            case!(empty_panel);
            case!(one_dot);
            case!(bare_dot_root);
            case!(three_dots);
            case!(numeral);
            case!(dots_apply_to_numeral);
            case!(nested_dots_coalesce);
            case!(nesting_is_preserved);
            case!(ambiguous_application_is_stuck);
            case!(sibling_transformers_compose_additively);
            case!(machine_agrees_with_chemistry);
            // sharing
            case!(shared_node_counts_each_time);
            case!(shared_node_settled_once_in_view);
            // order independence
            case!(sibling_order_is_not_meaning);
            // stepping
            case!(steps_until_done);
            case!(run_with_fuel_is_resumable);
            case!(step_before_load_fails);
            // determinism
            case!(deterministic);
            case!(reload_resets);
            // rejection
            case!(rejects_cycle);
            case!(rejects_self_loop);
            case!(rejects_dangling);
            case!(rejects_missing_root);
        }
    };
}
