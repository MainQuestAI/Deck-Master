use crate::error::Result;
use crate::model::Content;
use serde_json::Value;

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
            // Keep author spaces, including numbered labels ("1 数据与身份").
            // A space that only pads punctuation is still dropped.
            let remove = match (left, right) {
                (Some(a), Some(b)) => punctuation(b) || "（【《".contains(a),
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
            let has_value = fields.contains_key("value");
            for (key, value) in fields {
                // Preserve the cell's stored value and displayed spelling together.
                if key == "value" || (has_value && key == "display_text") {
                    continue;
                }
                if matches!(
                    key.as_str(),
                    "title" | "subtitle" | "heading" | "text" | "label" | "display_text"
                ) {
                    if let Value::String(original) = value {
                        *original = text(original);
                    }
                } else {
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
