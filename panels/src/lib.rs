//! panels — a visual functional programming language.
//!
//! The language core lives in [`lang`] as ordinary Rust with no dependency on
//! the browser; `SPEC.md` is its contract. This file is the thin layer that
//! binds the crate to the page at /panels.

pub mod lang;

use wasm_bindgen::prelude::*;

/// What the page says while the core has nothing else to say yet.
pub fn greeting() -> String {
    "hi wasm".to_string()
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
        assert_eq!(super::greeting(), "hi wasm");
    }
}
