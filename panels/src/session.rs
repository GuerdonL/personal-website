//! The page's handle on the core: parse a program, drive a machine one step
//! at a time, and describe the state as plain data. This is the whole
//! surface the page uses; it sees `MachineView` and nothing deeper
//! (SPEC §0.4, §4).

use wasm_bindgen::prelude::*;

use crate::lang::{parse, Cek, Machine, Node, NodeId, Program, Progress, Walker};

#[wasm_bindgen]
pub struct Session {
    program: Program,
    root: NodeId,
    machine: Box<dyn Machine>,
    machine_name: String,
    last: Progress,
}

#[wasm_bindgen]
impl Session {
    /// Parse `src` and load it into the named machine ("cek" or "walker").
    #[wasm_bindgen(constructor)]
    pub fn new(src: &str, machine: &str) -> Result<Session, String> {
        let (program, root) = parse(src).map_err(|e| e.to_string())?;
        let mut m: Box<dyn Machine> = match machine {
            "walker" => Box::new(Walker::default()),
            _ => Box::new(Cek::default()),
        };
        m.load(&program, root).map_err(|e| e.to_string())?;
        Ok(Session {
            program,
            root,
            machine: m,
            machine_name: if machine == "walker" { "walker" } else { "cek" }.into(),
            last: Progress::Running,
        })
    }

    pub fn step(&mut self) {
        self.last = self.machine.step();
    }

    pub fn run(&mut self, fuel: u32) {
        self.last = self.machine.run(fuel as u64);
    }

    pub fn reset(&mut self) {
        // load() resets; it cannot fail for a program that loaded once.
        let _ = self.machine.load(&self.program, self.root);
        self.last = Progress::Running;
    }

    pub fn done(&self) -> bool {
        self.last == Progress::Done
    }

    /// The program and the machine's view of it, as JSON. Hand-written so
    /// the crate carries no serialisation dependency; the shape is:
    ///
    /// ```json
    /// { "machine": "cek", "root": 3,
    ///   "nodes": [ {"id":0,"kind":"dot"}, {"id":1,"kind":"num","num":5},
    ///              {"id":2,"kind":"hole","depth":0},
    ///              {"id":3,"kind":"panel","children":[0,1]} ],
    ///   "focus": 1, "pending": [3,1], "steps": 4,
    ///   "settled": {"0":"+1","3":"6"}, "progress": "running" }
    /// ```
    pub fn view(&self) -> String {
        let v = self.machine.view();
        let mut s = String::with_capacity(1024);
        s.push_str(&format!(
            "{{\"machine\":\"{}\",\"root\":{},\"nodes\":[",
            self.machine_name, self.root.0
        ));
        for (i, id) in self.program.ids().enumerate() {
            if i > 0 {
                s.push(',');
            }
            s.push_str(&format!("{{\"id\":{}", id.0));
            match self.program.get(id) {
                Some(Node::Dot) => s.push_str(",\"kind\":\"dot\""),
                Some(Node::Num(n)) => s.push_str(&format!(",\"kind\":\"num\",\"num\":{n}")),
                Some(Node::Hole(d)) => s.push_str(&format!(",\"kind\":\"hole\",\"depth\":{d}")),
                Some(Node::Panel(kids)) | Some(Node::Binder(kids)) => {
                    let kind = if matches!(self.program.get(id), Some(Node::Binder(_))) {
                        "binder"
                    } else {
                        "panel"
                    };
                    s.push_str(&format!(",\"kind\":\"{kind}\",\"children\":["));
                    s.push_str(
                        &kids
                            .iter()
                            .map(|k| k.0.to_string())
                            .collect::<Vec<_>>()
                            .join(","),
                    );
                    s.push(']');
                }
                None => {}
            }
            s.push('}');
        }
        s.push_str("],\"focus\":");
        match v.focus {
            Some(f) => s.push_str(&f.0.to_string()),
            None => s.push_str("null"),
        }
        s.push_str(",\"pending\":[");
        s.push_str(
            &v.pending
                .iter()
                .map(|k| k.0.to_string())
                .collect::<Vec<_>>()
                .join(","),
        );
        s.push_str(&format!("],\"steps\":{},\"settled\":{{", v.steps));
        for (i, (id, val)) in v.settled.iter().enumerate() {
            if i > 0 {
                s.push(',');
            }
            s.push_str(&format!("\"{}\":{}", id.0, json_str(&val.to_string())));
        }
        s.push_str("},\"progress\":");
        match &self.last {
            Progress::Running => s.push_str("\"running\""),
            Progress::Done => s.push_str("\"done\""),
            Progress::Failed(e) => s.push_str(&json_str(&format!("failed: {e}"))),
        }
        s.push_str(",\"result\":");
        match self.machine.result() {
            Some(r) => s.push_str(&json_str(&r.to_string())),
            None => s.push_str("null"),
        }
        s.push('}');
        s
    }
}

fn json_str(s: &str) -> String {
    let mut out = String::with_capacity(s.len() + 2);
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn view_is_well_formed_json_and_steps() {
        let mut s = Session::new("{5 λ{• x̂}}", "cek").unwrap();
        assert!(!s.done());
        let v0 = s.view();
        assert!(v0.contains("\"progress\":\"running\""), "{v0}");
        s.run(1000);
        assert!(s.done());
        let v = s.view();
        assert!(v.contains("\"result\":\"6\""), "{v}");
        assert!(v.contains("\"kind\":\"binder\""), "{v}");
        // Balanced braces and brackets, at least.
        let depth = v.chars().fold(0i32, |d, c| match c {
            '{' | '[' => d + 1,
            '}' | ']' => d - 1,
            _ => d,
        });
        assert_eq!(depth, 0);
        s.reset();
        assert!(!s.done());
        assert!(s.view().contains("\"steps\":0"));
    }

    #[test]
    fn bad_programs_are_errors() {
        assert!(Session::new("{", "cek").is_err());
        assert!(Session::new("{x̂}", "cek").is_err());
    }
}
