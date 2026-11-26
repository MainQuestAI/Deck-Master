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

fn collect_content_ids(value: &Value, ids: &mut HashSet<String>) {
    match value {
        Value::Object(object) => {
            if let Some(Value::String(id)) = object.get("id")
                && !id.is_empty()
            {
                ids.insert(id.clone());
            }
            for child in object.values() {
                collect_content_ids(child, ids);
            }
        }
        Value::Array(array) => {
            for child in array {
                collect_content_ids(child, ids);
            }
        }
        _ => {}
    }
}

impl Content {
    pub fn collect_ids(&self) -> crate::error::Result<HashSet<String>> {
        let mut ids = HashSet::new();
        collect_content_ids(&serde_json::to_value(self)?, &mut ids);
        Ok(ids)
    }

    pub fn normalize_ids(&mut self) -> crate::error::Result<()> {
        self.normalize_ids_with_reserved(&HashSet::new())
    }

    pub fn normalize_ids_with_reserved(
        &mut self,
        extra_reserved: &HashSet<String>,
    ) -> crate::error::Result<()> {
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
        let mut reserved = extra_reserved.clone();
        collect_content_ids(&serde_json::to_value(&self)?, &mut reserved);
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

impl Evidence {
    fn meaningful(value: &Option<String>) -> Option<&str> {
        value.as_deref().filter(|text| !text.trim().is_empty())
    }

    pub fn has_ref(&self) -> bool {
        Self::meaningful(&self.r#ref).is_some()
    }

    pub fn has_gap(&self) -> bool {
        Self::meaningful(&self.gap).is_some()
    }

    pub fn gap_text(&self) -> Option<&str> {
        Self::meaningful(&self.gap)
    }
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
    pub kind: String,
    pub argument: Option<Argument>,
    pub image: Option<Artifact>,
    pub svg: Option<Artifact>,
    #[serde(default)]
    pub native: Option<Artifact>,
    pub preview: Option<String>,
    // Format-7 drafts written before the revision counter was retired persisted a
    // per-page `revision`. Accept it on read so those databases still open; it is
    // never written back and never read by any logic.
    #[serde(default, rename = "revision", skip_serializing)]
    pub legacy_revision: Option<u32>,
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
        // Whitespace-only ref/gap is absent. put stores that text and does not
        // reject a missing pair; run start does, for judgment pages.
        if item.has_ref() && item.has_gap() {
            return Err(crate::error::Error::Input(format!(
                "页面 {page_id} 的 evidence 第 {} 项同时有 ref 和 gap；二者互斥",
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
    // Design §3.4. A blank narrator clause, decision, or concern is omitted.
    let mut lines = Vec::new();
    let role = deck.brief.narrator.role.trim();
    let tone = deck.brief.narrator.tone.trim();
    let mut narrator = String::new();
    if !role.is_empty() {
        narrator.push_str(&format!("讲述人：{role}。"));
    }
    if !tone.is_empty() {
        narrator.push_str(&format!("语气：{tone}。"));
    }
    if !narrator.is_empty() {
        lines.push(narrator);
    }
    let decision = deck.brief.decision.trim().trim_end_matches('。');
    if !decision.is_empty() {
        lines.push(format!("待决事项：{decision}。"));
    }
    let concerns: Vec<&str> = deck
        .brief
        .concerns
        .iter()
        .map(|item| item.trim())
        .filter(|item| !item.is_empty())
        .collect();
    if !concerns.is_empty() {
        lines.push("读者关注点：".into());
        for concern in concerns {
            lines.push(format!("- {concern}"));
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

pub fn gap_list(pages: &[Page]) -> Value {
    // Design §3.4. Aggregate each page in order. Do not rewrite or dedupe text.
    // On one page, evidence gaps come before todos; the sample shows that source order.
    let mut items = Vec::new();
    for page in pages {
        if let Some(argument) = &page.argument {
            for item in &argument.evidence {
                let Some(gap) = item.gap_text() else {
                    continue;
                };
                items.push(serde_json::json!({
                    "page_id": page.id,
                    "source": "evidence",
                    "text": item.text,
                    "gap": gap,
                }));
            }
        }
        for todo in &page.todo {
            if todo.trim().is_empty() {
                continue;
            }
            items.push(serde_json::json!({
                "page_id": page.id,
                "source": "todo",
                "text": todo,
            }));
        }
    }
    serde_json::Value::Array(items)
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RunKind {
    Image,
    Svg,
    Native,
}

impl RunKind {
    pub fn parse(value: &str) -> crate::error::Result<Self> {
        match value {
            "image" => Ok(Self::Image),
            "svg" => Ok(Self::Svg),
            "native" => Ok(Self::Native),
            _ => Err(crate::error::Error::Input(
                "请选择 image、svg 或 native".into(),
            )),
        }
    }

    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Image => "image",
            Self::Svg => "svg",
            Self::Native => "native",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RunStatus {
    Open,
    Done,
    Cancelled,
}

impl RunStatus {
    pub fn parse(value: &str) -> Option<Self> {
        match value {
            "open" => Some(Self::Open),
            "done" => Some(Self::Done),
            "cancelled" => Some(Self::Cancelled),
            _ => None,
        }
    }

    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Open => "open",
            Self::Done => "done",
            Self::Cancelled => "cancelled",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RunPageState {
    Pending,
    Started,
    Done,
    Unadopted,
}

impl RunPageState {
    pub fn parse(value: &str) -> Option<Self> {
        match value {
            "pending" => Some(Self::Pending),
            "started" => Some(Self::Started),
            "done" => Some(Self::Done),
            "unadopted" => Some(Self::Unadopted),
            _ => None,
        }
    }

    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Pending => "pending",
            Self::Started => "started",
            Self::Done => "done",
            Self::Unadopted => "unadopted",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ReviewMethod {
    SelfCheck,
    OtherModel,
    Human,
}

impl ReviewMethod {
    pub fn parse(value: &str) -> crate::error::Result<Self> {
        match value {
            "self_check" => Ok(Self::SelfCheck),
            "other_model" => Ok(Self::OtherModel),
            "human" => Ok(Self::Human),
            _ => Err(crate::error::Error::Input(
                "审阅方式只接受 self_check、other_model 或 human".into(),
            )),
        }
    }

    pub const fn as_str(self) -> &'static str {
        match self {
            Self::SelfCheck => "self_check",
            Self::OtherModel => "other_model",
            Self::Human => "human",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ReviewRecordKind {
    Comment,
    ContentReview,
}

impl ReviewRecordKind {
    pub fn parse(value: &str) -> crate::error::Result<Self> {
        match value {
            "comment" => Ok(Self::Comment),
            "content_review" => Ok(Self::ContentReview),
            _ => Err(crate::error::Error::Input(
                "审阅类型只接受 comment 或 content_review".into(),
            )),
        }
    }

    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Comment => "comment",
            Self::ContentReview => "content_review",
        }
    }
}

impl Deck {
    pub fn page(&self, id: &str) -> Option<&Page> {
        self.pages.iter().find(|page| page.id == id)
    }
}
