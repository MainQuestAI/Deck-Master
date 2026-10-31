use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashSet;

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Brief {
    pub title: String,
    pub audience: String,
    pub task_type: String,
    pub goal: String,
    pub constraints: Vec<String>,
    pub page_limit: Option<u32>,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Pillar {
    pub title: String,
    pub points: Vec<String>,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Framing {
    pub thesis: String,
    pub pillars: Vec<Pillar>,
    pub facts: Vec<String>,
    pub assumptions: Vec<String>,
    pub questions: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Canvas {
    pub width_px: u32,
    pub height_px: u32,
    pub slide_width_in: f64,
    pub slide_height_in: f64,
}

impl Default for Canvas {
    fn default() -> Self {
        Self {
            width_px: 1280,
            height_px: 720,
            slide_width_in: 13.333,
            slide_height_in: 7.5,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Asset {
    pub id: String,
    pub file: String,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Style {
    pub canvas: Canvas,
    pub palette: Vec<String>,
    pub fonts: Vec<String>,
    pub assets: Vec<Asset>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Material {
    pub id: String,
    pub name: String,
    pub file: String,
    pub text_file: String,
    pub status: String,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct TextItem {
    pub id: String,
    pub text: String,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub children: Vec<TextItem>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tone: Option<String>,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Column {
    pub id: String,
    pub label: String,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Cell {
    pub id: String,
    pub column_id: String,
    pub display_text: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub value: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub unit: Option<String>,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Row {
    pub id: String,
    pub cells: Vec<Cell>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case", deny_unknown_fields)]
pub enum Block {
    Paragraph {
        #[serde(default)]
        id: String,
        #[serde(default)]
        text: String,
    },
    Bullets {
        #[serde(default)]
        id: String,
        #[serde(default)]
        heading: String,
        #[serde(default)]
        items: Vec<TextItem>,
    },
    Table {
        #[serde(default)]
        id: String,
        #[serde(default)]
        title: String,
        #[serde(default)]
        columns: Vec<Column>,
        #[serde(default)]
        rows: Vec<Row>,
    },
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Content {
    pub title: String,
    pub subtitle: String,
    pub body_blocks: Vec<Block>,
    pub labels: Vec<TextItem>,
    pub footnotes: Vec<TextItem>,
    pub callouts: Vec<TextItem>,
}

// IDs are deterministic so replaying an ID-free submission remains a no-op.
fn assign(id: &mut String, seen: &mut HashSet<String>, reserved: &HashSet<String>, next: &mut u64) {
    if !id.is_empty() && seen.insert(id.clone()) {
        return;
    }
    loop {
        let candidate = format!("a{next}");
        *next += 1;
        if !reserved.contains(&candidate) && seen.insert(candidate.clone()) {
            *id = candidate;
            return;
        }
    }
}

impl Content {
    pub fn normalize_ids(&mut self) -> crate::error::Result<()> {
        fn collect(value: &Value, ids: &mut HashSet<String>) {
            match value {
                Value::Object(object) => {
                    if let Some(Value::String(id)) = object.get("id") {
                        ids.insert(id.clone());
                    }
                    for child in object.values() {
                        collect(child, ids);
                    }
                }
                Value::Array(array) => {
                    for child in array {
                        collect(child, ids);
                    }
                }
                _ => {}
            }
        }
        fn items(
            values: &mut [TextItem],
            seen: &mut HashSet<String>,
            reserved: &HashSet<String>,
            next: &mut u64,
        ) {
            for item in values {
                assign(&mut item.id, seen, reserved, next);
                items(&mut item.children, seen, reserved, next);
            }
        }
        let mut reserved = HashSet::new();
        collect(&serde_json::to_value(&self)?, &mut reserved);
        let mut seen = HashSet::new();
        let mut next = 1;
        for block in &mut self.body_blocks {
            match block {
                Block::Paragraph { id, .. } => assign(id, &mut seen, &reserved, &mut next),
                Block::Bullets {
                    id, items: values, ..
                } => {
                    assign(id, &mut seen, &reserved, &mut next);
                    items(values, &mut seen, &reserved, &mut next);
                }
                Block::Table {
                    id, columns, rows, ..
                } => {
                    assign(id, &mut seen, &reserved, &mut next);
                    let original: Vec<_> = columns.iter().map(|c| c.id.clone()).collect();
                    for column in columns.iter_mut() {
                        assign(&mut column.id, &mut seen, &reserved, &mut next);
                    }
                    for row in rows {
                        assign(&mut row.id, &mut seen, &reserved, &mut next);
                        for (index, cell) in row.cells.iter_mut().enumerate() {
                            assign(&mut cell.id, &mut seen, &reserved, &mut next);
                            let position = if cell.column_id.is_empty()
                                || original.get(index) == Some(&cell.column_id)
                            {
                                Some(index)
                            } else {
                                original.iter().position(|id| id == &cell.column_id)
                            };
                            if let Some(column) = position.and_then(|i| columns.get(i)) {
                                cell.column_id = column.id.clone();
                            }
                        }
                    }
                }
            }
        }
        items(&mut self.labels, &mut seen, &reserved, &mut next);
        items(&mut self.footnotes, &mut seen, &reserved, &mut next);
        items(&mut self.callouts, &mut seen, &reserved, &mut next);
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Artifact {
    pub file: String,
    pub basis: String,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Page {
    pub id: String,
    pub purpose: String,
    pub layout: String,
    pub content: Content,
    pub notes: String,
    pub todo: Vec<String>,
    pub refs: Vec<String>,
    pub image: Option<Artifact>,
    pub svg: Option<Artifact>,
    pub preview: Option<String>,
}

impl Page {
    pub fn author(&self) -> PagePatch {
        PagePatch {
            id: self.id.clone(),
            purpose: Some(self.purpose.clone()),
            layout: Some(self.layout.clone()),
            content: Some(self.content.clone()),
            notes: Some(self.notes.clone()),
            todo: Some(self.todo.clone()),
            refs: Some(self.refs.clone()),
            image: None,
            svg: None,
            preview: None,
        }
    }
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Deck {
    pub brief: Brief,
    pub materials: Vec<Material>,
    pub framing: Framing,
    pub style: Style,
    pub pages: Vec<Page>,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PagePatch {
    pub id: String,
    pub purpose: Option<String>,
    pub layout: Option<String>,
    pub content: Option<Content>,
    pub notes: Option<String>,
    pub todo: Option<Vec<String>>,
    pub refs: Option<Vec<String>>,
    #[serde(skip_serializing)]
    pub image: Option<Value>,
    #[serde(skip_serializing)]
    pub svg: Option<Value>,
    #[serde(skip_serializing)]
    pub preview: Option<Value>,
}

impl PagePatch {
    pub fn apply(&self, page: &mut Page) {
        macro_rules! apply { ($($field:ident),*) => { $(if let Some(value) = &self.$field { page.$field = value.clone(); })* }; }
        apply!(purpose, layout, content, notes, todo, refs);
    }
}

#[derive(Debug, Default, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Patch {
    pub brief: Option<Brief>,
    pub framing: Option<Framing>,
    pub style: Option<Style>,
    pub order: Option<Vec<String>>,
    pub pages: Option<Vec<PagePatch>>,
    pub materials: Option<Value>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct Snapshot {
    pub version: i64,
    pub deck: Deck,
}
