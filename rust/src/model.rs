use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashSet;

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Narrator {
    pub role: String,
    pub tone: String,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Brief {
    pub title: String,
    pub audience: String,
    pub task_type: String,
    pub goal: String,
    pub constraints: Vec<String>,
    pub page_limit: Option<u32>,
    pub decision: String,
    pub concerns: Vec<String>,
    pub narrator: Narrator,
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
    pub storyline: Vec<String>,
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
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub pages: Vec<String>,
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub source: String,
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub license: String,
}

impl Asset {
    pub fn is_effective_for(&self, page_id: &str) -> bool {
        self.pages.is_empty() || self.pages.iter().any(|id| id == page_id)
    }
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
pub struct Evidence {
    #[serde(default)]
    pub text: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub r#ref: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub gap: Option<String>,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Argument {
    pub reasons: Vec<String>,
    pub evidence: Vec<Evidence>,
    pub reasoning: String,
    pub rebuttal: String,
}

pub const PAGE_KINDS: &[&str] = &["judgment", "explanation", "reference", "teaching"];

fn initial_revision() -> u32 {
    1
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Artifact {
    pub file: String,
    pub basis: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Page {
    pub id: String,
    pub purpose: String,
    pub layout: String,
    pub content: Content,
    pub notes: String,
    pub todo: Vec<String>,
    pub refs: Vec<String>,
    pub kind: String,
    pub argument: Option<Argument>,
    #[serde(default = "initial_revision")]
    pub revision: u32,
    pub image: Option<Artifact>,
    pub svg: Option<Artifact>,
    #[serde(default)]
    pub native: Option<Artifact>,
    pub preview: Option<String>,
}

impl Default for Page {
    fn default() -> Self {
        Self {
            id: String::new(),
            purpose: String::new(),
            layout: String::new(),
            content: Content::default(),
            notes: String::new(),
            todo: Vec::new(),
            refs: Vec::new(),
            kind: String::new(),
            argument: None,
            revision: 1,
            image: None,
            svg: None,
            native: None,
            preview: None,
        }
    }
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
            kind: Some(self.kind.clone()),
            argument: Some(self.argument.clone()),
            image: None,
            svg: None,
            native: None,
            preview: None,
        }
    }

    pub fn author_fields_changed(&self, other: &Page) -> bool {
        self.purpose != other.purpose
            || self.layout != other.layout
            || self.content != other.content
            || self.notes != other.notes
            || self.todo != other.todo
            || self.refs != other.refs
            || self.kind != other.kind
            || self.argument != other.argument
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
    #[serde(default)]
    pub kind: Option<String>,
    // Absent keeps the stored argument. null clears it. An object replaces it.
    #[serde(default, deserialize_with = "present_argument")]
    pub argument: Option<Option<Argument>>,
    #[serde(skip_serializing)]
    pub image: Option<Value>,
    #[serde(skip_serializing)]
    pub svg: Option<Value>,
    #[serde(skip_serializing)]
    pub native: Option<Value>,
    #[serde(skip_serializing)]
    pub preview: Option<Value>,
}

fn present_argument<'de, D>(
    deserializer: D,
) -> std::result::Result<Option<Option<Argument>>, D::Error>
where
    D: serde::Deserializer<'de>,
{
    Ok(Some(Option::<Argument>::deserialize(deserializer)?))
}

impl PagePatch {
    pub fn apply(&self, page: &mut Page) {
        macro_rules! apply { ($($field:ident),*) => { $(if let Some(value) = &self.$field { page.$field = value.clone(); })* }; }
        apply!(purpose, layout, content, notes, todo, refs, kind);
        if let Some(argument) = &self.argument {
            page.argument = argument.clone();
        }
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

pub fn assign_revisions(previous: Option<&Deck>, next: &mut Deck) {
    for page in &mut next.pages {
        match previous.and_then(|deck| deck.pages.iter().find(|prior| prior.id == page.id)) {
            Some(prior) => {
                let baseline = if prior.revision == 0 {
                    1
                } else {
                    prior.revision
                };
                page.revision = if prior.author_fields_changed(page) {
                    baseline.saturating_add(1)
                } else {
                    baseline
                };
            }
            None => page.revision = 1,
        }
    }
}

pub fn validate_kind(page_id: &str, kind: &str) -> crate::error::Result<()> {
    if kind.is_empty() || PAGE_KINDS.contains(&kind) {
        return Ok(());
    }
    Err(crate::error::Error::Input(format!(
        "页面 {page_id} 的 kind 只接受 judgment、explanation、reference、teaching 或留空；当前是 {kind}"
    )))
}

pub fn validate_argument(page_id: &str, argument: &Argument) -> crate::error::Result<()> {
    for (index, item) in argument.evidence.iter().enumerate() {
        let has_ref = item.r#ref.is_some();
        let has_gap = item.gap.is_some();
        if item.text.trim().is_empty() || has_ref == has_gap {
            return Err(crate::error::Error::Input(format!(
                "页面 {page_id} 的 evidence 第 {} 项必须有非空 text，并且只能填写 ref 或 gap 其中一项",
                index + 1
            )));
        }
    }
    Ok(())
}

pub fn missing_frame_fields(deck: &Deck) -> Vec<&'static str> {
    let mut missing = Vec::new();
    if deck.brief.audience.trim().is_empty() {
        missing.push("brief.audience");
    }
    if deck.brief.decision.trim().is_empty() {
        missing.push("brief.decision");
    }
    if deck
        .brief
        .concerns
        .iter()
        .all(|item| item.trim().is_empty())
    {
        missing.push("brief.concerns");
    }
    if deck.brief.narrator.role.trim().is_empty() {
        missing.push("brief.narrator.role");
    }
    if deck.brief.narrator.tone.trim().is_empty() {
        missing.push("brief.narrator.tone");
    }
    if deck
        .framing
        .storyline
        .iter()
        .all(|item| item.trim().is_empty())
    {
        missing.push("framing.storyline");
    }
    missing
}

pub fn writing_brief(deck: &Deck) -> String {
    let mut lines = Vec::new();
    let audience = deck.brief.audience.trim();
    if !audience.is_empty() {
        lines.push(format!("受众：{audience}"));
    }
    let decision = deck.brief.decision.trim();
    if !decision.is_empty() {
        lines.push(format!("要做的决定：{decision}"));
    }
    let concerns: Vec<&str> = deck
        .brief
        .concerns
        .iter()
        .map(|item| item.trim())
        .filter(|item| !item.is_empty())
        .collect();
    if !concerns.is_empty() {
        lines.push(format!("听众关心：{}", concerns.join("、")));
    }
    let role = deck.brief.narrator.role.trim();
    if !role.is_empty() {
        lines.push(format!("讲述人：{role}"));
    }
    let tone = deck.brief.narrator.tone.trim();
    if !tone.is_empty() {
        lines.push(format!("语气：{tone}"));
    }
    let beats: Vec<&str> = deck
        .framing
        .storyline
        .iter()
        .map(|item| item.trim())
        .filter(|item| !item.is_empty())
        .collect();
    if !beats.is_empty() {
        lines.push("故事线：".into());
        for (index, beat) in beats.iter().enumerate() {
            lines.push(format!("{}. {beat}", index + 1));
        }
    }
    lines.join("\n")
}

pub fn outline(pages: &[Page]) -> Value {
    serde_json::json!(
        pages
            .iter()
            .map(|page| serde_json::json!({
                "page_id": page.id,
                "kind": page.kind,
                "title": page.content.title,
            }))
            .collect::<Vec<_>>()
    )
}
