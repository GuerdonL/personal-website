# panels

A visual functional programming language. The core is Rust; the page at
`/panels` is that core compiled to WebAssembly.

## Layout

- `src/lib.rs` — the crate. `core` is pure Rust (run `cargo test`); the
  `#[wasm_bindgen(start)]` entry binds it to the page.
- `web/index.html` — the page shell. It imports `./pkg/panels.js`, which the
  build generates; `pkg/` is not committed.
- The site workflow (`.github/workflows/build.yml`) compiles the crate for
  `wasm32-unknown-unknown`, runs `wasm-bindgen --target web`, and copies
  `web/` plus `pkg/` to the deployed `/panels`.

## Building locally

```sh
rustup target add wasm32-unknown-unknown
cargo install wasm-bindgen-cli --version 0.2.129   # must match Cargo.toml
cd panels
cargo build --release --target wasm32-unknown-unknown
wasm-bindgen --target web --out-dir pkg --no-typescript \
  target/wasm32-unknown-unknown/release/panels.wasm
python3 -m http.server   # then open http://localhost:8000/web/
```
