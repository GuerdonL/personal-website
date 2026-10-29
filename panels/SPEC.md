# panels — language specification

**Status:** v0 draft. This document is the contract that every implementation
in this crate is written against. Change the spec first, then the code.

---

## 0. Philosophy

1. **Interfaces before implementations.** The data model and the traits in
   `src/lang/` are the product. Evaluators, type checkers, layout engines and
   serializers are plugins that implement those traits and may be swapped
   without touching anything else.
2. **Every interface is validated by two implementations.** An interface that
   has only ever been implemented once is a guess. Nothing is built *on top of*
   an interface until two independent implementations pass the same
   conformance suite without contortion.
3. **Strategy and rules are separate plugins.** *What* two things do when they
   meet is chemistry (`chemistry.rs`). *In what order* an evaluator makes
   things meet is strategy (`machine.rs`). A machine may never hard-code a
   reaction, and the chemistry may never assume an order.
4. **The core knows nothing about pixels.** Layout, gestures and rendering live
   outside `lang/` and consume only `Program`, `Value` and `MachineView`.

---

## 1. The law

> **Juxtaposition is commutative. Nesting is ordered.**

A program is a tree of *panels*. A panel holds a multiset of children, each of
which is a leaf or another panel. Children of one panel have **no order** and
**no position**: two programs that differ only in the arrangement of siblings
are the same program. All sequence, all argument order, all structure that is
not commutative is expressed by nesting.

Consequences:

- A program is fully described by a multiset of multisets. Two programs are
  equal iff those are structurally equal. Layout is never part of meaning.
- Lists are right-nested panels: `[1, 0, 8]` is `{1 {0 {8}}}`. Numerals,
  strings, vectors and matrices are all lists under this reading; the *fold*
  that interprets a list (Horner's rule, row-by-column, concatenation) is
  supplied by whichever primitive consumes it, never by the core.
- Functions of several non-interchangeable arguments take them as a nested
  chain. This is currying, and it is the only mechanism.
- There is **no reduction-order question**. Because siblings commute, an
  evaluator may reduce them in any order, or in parallel, and must arrive at
  the same result. This is a *requirement on the chemistry* (§3.3), not a
  property the machine has to arrange.

This model is a known one: it is a chemical abstract machine (Berry & Boudol,
1990) / Gamma (Banâtre & Le Métayer) with membranes, as in P systems. Panels
are membranes, leaves are molecules, and evaluation is reaction. The names are
ours; the mathematics is theirs, and the literature on confluence for these
systems applies directly.

---

## 2. Terms — the program graph

Defined in `src/lang/term.rs`.

```
Program  = arena of Node, addressed by NodeId
Node     = Panel(children: multiset<NodeId>)   -- a membrane
         | Binder(children: multiset<NodeId>)  -- a membrane with a port: λ
         | Hole(depth: u32)                    -- a use of a bound value, a leaf
         | Dot                                 -- the additive unit, a leaf
         | Num(i64)                            -- a numeral literal, a leaf
```

- The arena is a **DAG**, not a tree: a `NodeId` may be the child of several
  panels. That *is* sharing (a `let`); there is no separate reference node.
  A node reachable from itself is a **cycle** and is rejected at load time.
- `children` is stored as a `Vec` for convenience but its order is not
  observable. Implementations must not depend on it, and the conformance
  suite shuffles it.
- A **dot** is the curried function `+1`. It is a leaf, it is a function, and
  it is a value; "functions are first-class" is not a feature here, it is the
  only thing there is.
- A **binder** is a panel with a port on its wall: a function of one
  argument. It is the only way a value gets *into* a panel that was written
  with something missing. A binder is a value in its own right (a closure,
  §3.1) and does not evaluate its children until it meets an argument.
- A **hole** is a use of the argument. `Hole(d)` refers to the `d`-th
  enclosing *binder* (not panel), innermost first — a de Bruijn index. A
  program whose root has an unbound hole is rejected at load. Functions of
  several arguments are nested binders, so `{x̂ {ŷ …}}` is `λx. λy. …` and
  argument order is nesting order, per the law.
- A node is **closed** if it contains no hole that escapes it. Only closed
  nodes have a value independent of context, so only closed nodes may be
  memoised by `NodeId`; an open node is evaluated per path, under an
  environment.
- A **numeral** is sugar. `108` *denotes* the nest `{1 {0 {8}}}` under the
  base-10 fold; v0 stores it as a leaf for convenience and does not yet expand
  it. (Open question §6.)

### 2.1 Deferred from v0

Additional dot families (multiplicative, imaginary), strings, and explicit
thunks. Each will be added by amending this document first.

---

### 2.2 Notation

`src/lang/text.rs` is a way to write a program down; it is not the language.
`{…}` is a panel, `λ{…}` a binder, `•` a dot, `x̂ ŷ ẑ` (or `^0 ^1 ^2`) holes,
digits a numeral, and `name = expr;` defines a node that later mentions share.
Sibling order in the text means nothing. This document uses it from here on.

## 3. Values and chemistry

Defined in `src/lang/value.rs` and `src/lang/chemistry.rs`.

### 3.1 Values

```
Value = Num(i64)                 -- a datum
      | Add(i64)                 -- a transformer: the function  x ↦ x + n
      | Closure(body: NodeId, env: Vec<Value>)
                                 -- a transformer: a binder with the values of
                                 -- its enclosing binders, innermost last
      | Bag(sorted Vec<Value>)   -- a settled multiset that would not react further
```

A `Closure` is a transformer. `Add n` is just the closure the language
provides for free. Equality on closures is structural: same binder node, equal
environments. For that to be meaningful the environment is **trimmed at
capture** to exactly the values the binder's holes can reach (its free depth,
§2): a closed binder captures nothing, so the same function made in two
places is the same value.

`Value` has a **canonical form**: a `Bag` is kept sorted, so structural
equality on `Value` is equality of multisets. Constructors enforce this;
nothing may construct an unsorted `Bag`.

A `Bag` is what data *is*. A list is a bag that happened not to react; a
matrix is nested bags. There is no separate data constructor because "stuck"
and "data" are the same thing in a chemical model.

### 3.2 Reaction

`react(a, b) -> Option<Reaction>` is the complete pairwise chemistry of v0.
A reaction is either a finished value or *work for the machine*:

```
Reaction = Value(Value)
         | Apply(closure: Closure, arg: Value)   -- evaluate the binder's
                                                 -- children under env + arg,
                                                 -- then settle them
```

| a          | b         | result                      |
|------------|-----------|-----------------------------|
| `Add(m)`   | `Add(n)`  | `Value(Add(m + n))`         |
| `Add(n)`   | `Num(x)`  | `Value(Num(x + n))`         |
| `Closure`  | any datum | `Apply(closure, datum)`     |
| anything else          | *no reaction*               |

`react` is **commutative** by construction (`react(a,b) == react(b,a)`).
It never evaluates anything: chemistry says *what* two molecules do, the
machine decides *when* (§0.3). `Closure` meets `Closure` and `Add` meets
`Closure` do not react: functions do not flow (§6.6).

### 3.3 Settling a panel

`settle(molecules) -> Settled` turns the evaluated children of a panel into
the panel's value, or into the one application that produces it. It is
defined in terms of `react` and is the *only* place where the shape of a whole
bag matters:

1. **Coalesce transformers.** While any two transformers react, replace them
   with their product. This is associative and commutative, so the result is
   unique.
2. **Apply.** If exactly one transformer and exactly one datum remain and they
   react, the result is their reaction — a value, or an `Apply` the machine
   must now run; the application's result *is* the panel's value (which may
   itself be a closure: that is currying). If there are several data, nothing
   applies — the bag is stuck as it stands. (This rule is what makes settling
   confluent: a transformer never has to choose a victim.)
3. **Unwrap.** If exactly one molecule remains, it *is* the panel's value.
   Otherwise the panel's value is the `Bag` of what remains. An empty panel is
   `Bag([])`.

Examples (`•` is a dot):

```
{}                 = Bag[]
{•}                = Add 1
{• • •}            = Add 3
{5 • •}            = Num 7
{• {• •}}          = Add 3           -- inner settles to Add 2, then coalesces
{1 {0 {8}}}        = Bag[Num 1, Bag[Num 0, Num 8]]   -- data; nothing reacts
{• 1 2}            = Bag[Add 1, Num 1, Num 2]        -- ambiguous, so stuck
```

With binders (`x̂` is `Hole 0`, `ŷ` is `Hole 1`, `λ{…}` is a binder):

```
λ{x̂}                 = Closure                   -- a value; nothing runs
{5 λ{x̂}}             = Num 5                     -- identity
{5 λ{• x̂}}           = Num 6                     -- the function x ↦ x + 1, by hand
{5 λ{x̂ x̂}}           = Bag[Num 5, Num 5]         -- one argument, used twice
{4 {3 λ{λ{ŷ {x̂}}}}}  = Bag[Num 3, Num 4]         -- curried pair: outer binds 3
{λ{x̂} {1 {0 {8}}}}   = Bag[Num 1, Bag[Num 0, Num 8]]   -- a closure takes a bag
{λ{x̂} λ{x̂}}          = Bag[Closure, Closure]     -- stuck: closures do not meet
```

Note that `{•••} {••}` as siblings gives `Add 5`, not 6: two additive
transformers compose additively. Multiplication is a different family of dot
and is deferred (§2.1).

### 3.4 The confluence requirement

Any future addition to the chemistry must keep `settle` **order-independent**:
for every multiset of molecules, every reaction order reaches the same
canonical `Value`. The conformance suite enforces this by property test over
shuffled inputs. A primitive that would break it is rejected, not special-cased
in a machine.

---

## 4. Machines — the evaluation contract

Defined in `src/lang/machine.rs`.

```rust
pub trait Machine {
    fn load(&mut self, program: &Program, root: NodeId) -> Result<(), LoadError>;
    fn step(&mut self) -> Progress;        // exactly one unit of work
    fn view(&self) -> MachineView;         // what the UI is allowed to see
    fn result(&self) -> Option<&Value>;    // Some once Progress::Done

    fn run(&mut self, fuel: u64) -> Progress { /* default: step until not Running or fuel out */ }
}
```

- `load` validates (cycle check, dangling ids) and resets the machine. A
  machine may be loaded many times.
- `step` performs *one unit of work* as the machine defines it, and returns
  `Running`, `Done`, or `Failed(Error)`. After `Done` or `Failed`, further
  `step`s are no-ops returning the same answer. Every machine must terminate
  in a finite number of steps for every finite acyclic program.
- `view` returns a `MachineView`: the node currently in focus, the nodes
  already settled with their values, and the pending work as a list of node
  ids from outermost to innermost. This is the whole interface between a
  machine and the UI. The UI never sees a continuation, an environment or a
  stack frame; if a future machine has none of those, it still produces a
  `MachineView`.
- `result` is `Some` iff the last `Progress` was `Done`, and then equals
  `view().settled[root]`.
- `settled` holds **closed** nodes only (§2). An open node has no value of
  its own, and a machine must not report one for it. A machine must report
  every closed node whose value it has computed (so the root, once `Done`),
  and may report any other closed node; two machines may therefore differ in
  *which* closed nodes they list, never in the values.
- Every machine must terminate for every valid v0 program. This holds
  because closures cannot be applied to closures (§3.2, §6.6), so there is
  no self-application and hence no non-terminating term.

The contract deliberately says nothing about *how* a machine reduces. The v0
implementations will be (a) a recursive tree-walker, which is the trivial
reading of §3, and (b) a CEK-style machine with an explicit control stack,
which is the one the UI will animate. Both must pass `conformance.rs`
unchanged. Graph reduction or interaction nets would be further `Machine`s.

---

## 5. Conformance

`src/lang/conformance.rs` is the executable form of this document. It is
generic over `M: Machine + Default` and is instantiated per implementation
with `conformance_tests!(MyMachine);`. The suite is the authority; where this
prose and the suite disagree, fix whichever is wrong and say so in the commit.

Categories:

- **Settling** — every example in §3.3.
- **Sharing** — a node that is a child of two panels is evaluated as a value
  both times (`{P P}` where `P = {••}` is `Add 4`).
- **Order independence** — a program and the same program with every
  `children` vector shuffled settle to equal values.
- **Stepping** — `step` returns `Running` with `view().focus == Some(_)` until
  `Done`; `run(fuel)` with insufficient fuel returns `Running` and can be
  resumed; `result()` is `None` until `Done`.
- **Determinism** — loading and running the same program twice gives equal
  results and equal step counts.
- **Binders** — every example in §3.3; a shared binder applied in two
  places; order independence over a program with binders; closed sub-nodes
  of an open binder body are still memoised.
- **Rejection** — a cyclic program fails `load` with `LoadError::Cycle`; a
  dangling id fails with `LoadError::Dangling`; a hole that escapes the root
  fails with `LoadError::UnboundHole`.

---

## 6. Open questions

Recorded so they are decided deliberately, not by accident of implementation.

1. **Numerals.** Should `Num(108)` be expanded to `{1 {0 {8}}}` on load so
   that the core has one representation, with the leaf kept only as notation?
   Leaning yes once a fold primitive exists.
2. **Spines.** The intended rendering of a right-nested chain is a single row
   of cells (as Lisp prints `(1 0 8)`, not the cons cells). This is a renderer
   concern and must not leak into the data model, but the model should make
   the chain cheap to detect.
3. **Binders** — *decided*: filled by the molecule that meets the panel,
   with de Bruijn holes (§2). A distinguished argument slot was rejected
   because it would make `{1 {0 {8}}}` an application. Point-free
   combinators remain a possible *lowering* of binders, not a surface.
4. **Multiple transformer families.** When additive and multiplicative dots
   share a panel, do they coalesce within family only (stuck as a bag of two
   transformers) or is there a cross-family rule (distributivity)? Must be
   settled with a confluence proof, not a test.
5. **Bags as arguments.** `Add n` does not react with a `Bag`; a `Closure`
   takes one whole. Mapping over data is the first thing users will want; it
   should be a primitive, not an implicit rule.
6. **Functions do not flow** — *decided*. Two closures in a bag do not
   react, because neither is a datum and a transformer never chooses a
   victim; and nothing is added to make them. A closure applies to data and
   is never itself an argument. Where a textual language passes `f` to
   `map`, a panels program puts `f` inside each element's panel and shares
   the one definition: `{{1 f} {{2 f} {{3 f}}}}`. The function sits where
   its argument is, which is what "all computation happens in the leaves"
   means. Consequences: no `twice f`, no `fold op`, no hole ever holds a
   closure, no self-application, and every program terminates. If
   abstracting over *which* function ever becomes necessary, the escape is
   still nesting (a membrane that does not dissolve around a closure), as
   an amendment here first.
