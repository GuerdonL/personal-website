//! panels — a visual functional programming language.
//!
//! The language core lives in [`lang`] as ordinary Rust with no dependency on
//! the browser; `SPEC.md` is its contract. This file is the thin layer that
//! binds the crate to the page at /panels.

pub mod lang;

use wasm_bindgen::prelude::*;

use lang::{Cek, Machine, Progress, Walker};

/// What the page says while the core has nothing else to say yet: hello,
/// and the spec's `{{••• ••}}` example evaluated by both machines.
pub fn greeting() -> String {
    let mut lines = vec!["hi wasm".to_string()];
    for text in ["{{•••} {••}}", "{5 λ{• x̂}}", "{4 {3 λ{λ{ŷ {x̂}}}}}"] {
        let (p, root) = match lang::parse(text) {
            Ok(x) => x,
            Err(e) => {
                lines.push(format!("{text}: {e}"));
                continue;
            }
        };
        for (name, mut m) in [
            ("walker", Box::new(Walker::default()) as Box<dyn Machine>),
            ("cek", Box::new(Cek::default())),
        ] {
            let line = match m.load(&p, root).map(|_| m.run(1_000)) {
                Ok(Progress::Done) => format!(
                    "{text} = {} ({name}, {} steps)",
                    m.result().expect("done"),
                    m.view().steps
                ),
                Ok(other) => format!("{name}: {other:?}"),
                Err(e) => format!("{name}: {e}"),
            };
            lines.push(line);
        }
    }
    lines.join("\n")
}

/// Entry point: runs automatically when the wasm module is instantiated.
#[wasm_bindgen(start)]
pub fn start() -> Result<(), JsValue> {
    console_error_panic_hook::set_once();

    let window = web_sys::window().ok_or("no window")?;
    let document = window.document().ok_or("no document")?;
    let stage = document
        .get_element_by_id("stage")
        .ok_or("no #stage element on the page")?;

    stage.set_text_content(Some(&greeting()));
    web_sys::console::log_1(&JsValue::from_str("panels: wasm module started"));
    Ok(())
}

#[cfg(test)]
mod tests {
    #[test]
    fn greets() {
        let g = super::greeting();
        assert!(g.starts_with("hi wasm\n"), "{g}");
        assert!(g.contains("{{•••} {••}} = +5 (walker,"), "{g}");
        assert!(g.contains("{{•••} {••}} = +5 (cek,"), "{g}");
        assert!(g.contains("{5 λ{• x̂}} = 6 (walker,"), "{g}");
        assert!(g.contains("{5 λ{• x̂}} = 6 (cek,"), "{g}");
        assert!(g.contains("{4 {3 λ{λ{ŷ {x̂}}}}} = {3 4} (cek,"), "{g}");
    }
}
