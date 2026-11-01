use crate::error::Result;
use crate::model::Content;
use serde_json::Value;

pub const RULES: &str = include_str!("../../deck-skill/references/expression-review-humanizer.md");

fn han(c: char) -> bool {
    ('\u{3400}'..='\u{9fff}').contains(&c)
}

fn punctuation(c: char) -> bool {
    "，。、；：！？）】》％%".contains(c)
}

pub fn text(input: &str) -> String {
    let chars: Vec<_> = input.chars().collect();
    let mut output = String::new();
    let mut index = 0;
    while index < chars.len() {
        if chars[index] == ' ' || chars[index] == '\u{3000}' {
            let start = index;
            while index < chars.len() && matches!(chars[index], ' ' | '\u{3000}') {
                index += 1;
            }
            let left = start.checked_sub(1).map(|i| chars[i]);
            let right = chars.get(index).copied();
            let remove = match (left, right) {
                (Some(a), Some(b)) => {
                    (han(a) && b.is_ascii_digit())
                        || (a.is_ascii_digit() && han(b))
                        || punctuation(b)
                        || ("（【《".contains(a))
                }
                _ => false,
            };
            if !remove {
                output.extend(&chars[start..index]);
            }
        } else {
            output.push(chars[index]);
            index += 1;
        }
    }
    output
}

pub fn normalize(value: &mut Value) {
    match value {
        Value::Array(values) => values.iter_mut().for_each(normalize),
        Value::Object(fields) => {
            for (key, value) in fields {
                if matches!(
                    key.as_str(),
                    "title" | "subtitle" | "heading" | "text" | "label" | "display_text"
                ) {
                    if let Value::String(original) = value {
                        *original = text(original);
                    }
                } else if key != "value" {
                    normalize(value);
                }
            }
        }
        _ => {}
    }
}

pub fn content(input: &Content) -> Result<Content> {
    let mut value = serde_json::to_value(input)?;
    normalize(&mut value);
    Ok(serde_json::from_value(value)?)
}
