//! panels — a visual functional programming language.
//!
//! The language core will live in this crate as ordinary Rust, with no
//! dependency on the browser; `web.rs` is the thin layer that binds it to
//! the page at /panels. For now the only thing the core knows how to say
//! is hello.

use wasm_bindgen::prelude::*;

/// The language core. Pure Rust, testable natively with `cargo test`.
pub mod core {
    /// What the program says when it has nothing else to say yet.
    pub fn greeting() -> String {
        "hi wasm".to_string()
    }
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

    stage.set_text_content(Some(&core::greeting()));
    web_sys::console::log_1(&JsValue::from_str("panels: wasm module started"));
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::core;

    #[test]
    fn greets() {
        assert_eq!(core::greeting(), "hi wasm");
    }
}
