//! panels — a visual functional programming language.
//!
//! The language core lives in [`lang`] as ordinary Rust with no dependency on
//! the browser; `SPEC.md` is its contract. This file is the thin layer that
//! binds the crate to the page at /panels.

pub mod lang;

use wasm_bindgen::prelude::*;

use lang::{Cek, Machine, Program, Progress, Walker};

/// What the page says while the core has nothing else to say yet: hello,
/// and the spec's `{{••• ••}}` example evaluated by both machines.
pub fn greeting() -> String {
    let mut p = Program::new();
    let a = p.dots(3);
    let b = p.dots(2);
    let sum = p.panel([a, b]);
    let x = p.hole(0);
    let d = p.dot();
    let inc = p.binder([x, d]);
    let five = p.num(5);
    let applied = p.panel([five, inc]);

    let mut lines = vec!["hi wasm".to_string()];
    for (text, root) in [("{••• ••}", sum), ("{5 λ{• x̂}}", applied)] {
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
        assert!(g.contains("{••• ••} = +5 (walker,"), "{g}");
        assert!(g.contains("{••• ••} = +5 (cek,"), "{g}");
        assert!(g.contains("{5 λ{• x̂}} = 6 (walker,"), "{g}");
        assert!(g.contains("{5 λ{• x̂}} = 6 (cek,"), "{g}");
    }
}
