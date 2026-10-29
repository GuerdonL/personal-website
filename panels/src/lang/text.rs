//! A textual notation for programs, for tests, docs and the page. It is
//! *not* the language: the program graph is (SPEC §2). This is just a way to
//! write one down.
//!
//! ```text
//! program  := (def ';')* expr
//! def      := name '=' expr                -- a shared node; use it by name
//! expr     := '{' expr* '}'                -- panel
//!           | ('λ' | '\') '{' expr* '}'    -- binder
//!           | '•' | '.'                    -- dot
//!           | '-'? digits                  -- numeral
//!           | '^' digits?                  -- hole, ^ alone is ^0
//!           | 'x̂' | 'ŷ' | 'ẑ'              -- holes 0, 1, 2 (sugar)
//!           | name                         -- a defined node
//! ```
//!
//! Whitespace and commas separate; `#` starts a comment to end of line.
//! Sibling order in the text is kept in the `Vec` but means nothing.

use std::collections::HashMap;
use std::fmt;

use super::term::{Node, NodeId, Program};

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ParseError {
    pub at: usize,
    pub msg: String,
}

impl fmt::Display for ParseError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "at {}: {}", self.at, self.msg)
    }
}

impl std::error::Error for ParseError {}

/// Parse a program. Returns the arena and the root (the final expression).
pub fn parse(src: &str) -> Result<(Program, NodeId), ParseError> {
    let mut p = Parser {
        chars: src.char_indices().peekable(),
        src,
        program: Program::new(),
        names: HashMap::new(),
    };
    let root = p.program_()?;
    Ok((p.program, root))
}

struct Parser<'a> {
    chars: std::iter::Peekable<std::str::CharIndices<'a>>,
    src: &'a str,
    program: Program,
    names: HashMap<String, NodeId>,
}

impl Parser<'_> {
    fn pos(&mut self) -> usize {
        self.chars.peek().map(|&(i, _)| i).unwrap_or(self.src.len())
    }

    fn err<T>(&mut self, msg: impl Into<String>) -> Result<T, ParseError> {
        Err(ParseError {
            at: self.pos(),
            msg: msg.into(),
        })
    }

    fn skip_ws(&mut self) {
        while let Some(&(_, c)) = self.chars.peek() {
            if c == '#' {
                for (_, c) in self.chars.by_ref() {
                    if c == '\n' {
                        break;
                    }
                }
            } else if c.is_whitespace() || c == ',' {
                self.chars.next();
            } else {
                break;
            }
        }
    }

    fn peek(&mut self) -> Option<char> {
        self.skip_ws();
        self.chars.peek().map(|&(_, c)| c)
    }

    fn eat(&mut self, want: char) -> bool {
        if self.peek() == Some(want) {
            self.chars.next();
            true
        } else {
            false
        }
    }

    fn expect(&mut self, want: char) -> Result<(), ParseError> {
        if self.eat(want) {
            Ok(())
        } else {
            self.err(format!("expected '{want}'"))
        }
    }

    fn program_(&mut self) -> Result<NodeId, ParseError> {
        loop {
            // A definition is `name = …`; look ahead for the '='.
            if let Some(c) = self.peek() {
                if is_name_start(c) {
                    let save = self.chars.clone();
                    let name = self.name();
                    if self.eat('=') {
                        let id = self.expr()?;
                        if self.names.insert(name.clone(), id).is_some() {
                            return self.err(format!("'{name}' defined twice"));
                        }
                        if !self.eat(';') {
                            return self.err("expected ';' after definition");
                        }
                        continue;
                    }
                    self.chars = save;
                }
            }
            break;
        }
        let root = self.expr()?;
        if self.peek().is_some() {
            return self.err("unexpected text after the root expression");
        }
        Ok(root)
    }

    fn name(&mut self) -> String {
        let mut s = String::new();
        while let Some(&(_, c)) = self.chars.peek() {
            if is_name_char(c) {
                s.push(c);
                self.chars.next();
            } else {
                break;
            }
        }
        s
    }

    fn digits(&mut self) -> Option<i64> {
        let mut s = String::new();
        while let Some(&(_, c)) = self.chars.peek() {
            if c.is_ascii_digit() {
                s.push(c);
                self.chars.next();
            } else {
                break;
            }
        }
        s.parse().ok()
    }

    fn body(&mut self) -> Result<Vec<NodeId>, ParseError> {
        self.expect('{')?;
        let mut kids = Vec::new();
        loop {
            match self.peek() {
                None => return self.err("unclosed '{'"),
                Some('}') => {
                    self.chars.next();
                    return Ok(kids);
                }
                Some(_) => kids.push(self.expr()?),
            }
        }
    }

    fn expr(&mut self) -> Result<NodeId, ParseError> {
        let Some(c) = self.peek() else {
            return self.err("expected an expression");
        };
        match c {
            '{' => {
                let kids = self.body()?;
                Ok(self.program.panel(kids))
            }
            'λ' | '\\' => {
                self.chars.next();
                let kids = self.body()?;
                Ok(self.program.binder(kids))
            }
            '•' | '.' => {
                self.chars.next();
                Ok(self.program.dot())
            }
            '^' => {
                self.chars.next();
                let d = self.digits().unwrap_or(0);
                Ok(self.program.hole(d as u32))
            }
            '-' => {
                self.chars.next();
                match self.digits() {
                    Some(n) => Ok(self.program.num(-n)),
                    None => self.err("expected digits after '-'"),
                }
            }
            c if c.is_ascii_digit() => {
                let n = self.digits().expect("digits");
                Ok(self.program.num(n))
            }
            c if is_name_start(c) => {
                let name = self.name();
                // x̂ ŷ ẑ: a letter followed by a combining circumflex.
                // Both the decomposed (x + U+0302) and precomposed (ŷ U+0177,
                // ẑ U+1E91) spellings; keyboards and editors differ.
                match name.as_str() {
                    "x\u{302}" => return Ok(self.program.hole(0)),
                    "y\u{302}" | "\u{177}" => return Ok(self.program.hole(1)),
                    "z\u{302}" | "\u{1e91}" => return Ok(self.program.hole(2)),
                    _ => {}
                }
                match self.names.get(&name) {
                    Some(&id) => Ok(id),
                    None => self.err(format!("'{name}' is not defined")),
                }
            }
            other => self.err(format!("unexpected '{other}'")),
        }
    }
}

fn is_name_start(c: char) -> bool {
    c.is_alphabetic() && c != 'λ' || c == '_'
}

fn is_name_char(c: char) -> bool {
    is_name_start(c) || c.is_ascii_digit() || c == '\'' || c == '\u{302}'
}

/// Write a node back out. Shared nodes are inlined at each use, so the text
/// loses sharing; it is for reading, not round-tripping DAGs.
pub fn print(program: &Program, root: NodeId) -> String {
    let mut out = String::new();
    write_node(program, root, &mut out);
    out
}

fn write_node(program: &Program, id: NodeId, out: &mut String) {
    match program.get(id) {
        Some(Node::Dot) => out.push('•'),
        Some(Node::Num(n)) => out.push_str(&n.to_string()),
        Some(Node::Hole(0)) => out.push_str("x\u{302}"),
        Some(Node::Hole(1)) => out.push_str("y\u{302}"),
        Some(Node::Hole(2)) => out.push_str("z\u{302}"),
        Some(Node::Hole(d)) => out.push_str(&format!("^{d}")),
        Some(Node::Panel(kids)) | Some(Node::Binder(kids)) => {
            if matches!(program.get(id), Some(Node::Binder(_))) {
                out.push('λ');
            }
            out.push('{');
            for (i, &k) in kids.iter().enumerate() {
                // Runs of dots print together: {••• 5}, not {• • • 5}.
                let dot = matches!(program.get(k), Some(Node::Dot));
                let prev_dot = i > 0 && matches!(program.get(kids[i - 1]), Some(Node::Dot));
                if i > 0 && !(dot && prev_dot) {
                    out.push(' ');
                }
                write_node(program, k, out);
            }
            out.push('}');
        }
        None => out.push_str(&format!("?{id}")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn roundtrip(s: &str) {
        let (p, r) = parse(s).unwrap();
        assert_eq!(print(&p, r), s);
    }

    #[test]
    fn prints_what_it_parsed() {
        roundtrip("{••• {5 •}}");
        roundtrip("{5 λ{• x\u{302}}}");
        roundtrip("{4 {3 λ{λ{y\u{302} {x\u{302}}}}}}");
        roundtrip("{1 {0 {8}}}");
        roundtrip("{-3 ^4}");
        roundtrip("{}");
    }

    #[test]
    fn ascii_spellings() {
        let (p, r) = parse("\\{. ^ ^1 \u{177}}").unwrap();
        assert_eq!(print(&p, r), "λ{• x\u{302} y\u{302} y\u{302}}");
    }

    #[test]
    fn definitions_share() {
        let (p, r) = parse("two = {••}; {two two}").unwrap();
        let kids = p.children(r);
        assert_eq!(kids.len(), 2);
        assert_eq!(kids[0], kids[1], "a name is one node, used twice");
    }

    #[test]
    fn comments_and_commas() {
        let (p, r) = parse("# a comment\n{1, 2, # inline\n 3}").unwrap();
        assert_eq!(p.children(r).len(), 3);
    }

    #[test]
    fn errors_point_somewhere() {
        assert!(parse("{").is_err());
        assert!(parse("{} }").is_err());
        assert!(parse("nope").unwrap_err().msg.contains("not defined"));
        assert!(parse("a = 1; a = 2; a").unwrap_err().msg.contains("twice"));
        assert!(parse("a = 1 a").is_err());
    }
}
