use crate::model::{Block, Deck, TextItem};

fn bullets(output: &mut String, values: &[TextItem], depth: usize) {
    for item in values {
        output.push_str(&format!("{}- {}\n", "  ".repeat(depth), item.text));
        bullets(output, &item.children, depth + 1);
    }
}

fn list(output: &mut String, label: &str, values: &[String]) {
    if !values.is_empty() {
        output.push_str(&format!("\n**{label}**\n\n"));
        for value in values {
            output.push_str(&format!("- {value}\n"));
        }
    }
}

fn cell(text: &str) -> String {
    text.replace('|', "\\|").replace('\n', "<br>")
}

pub fn markdown(deck: &Deck) -> String {
    let mut output = format!("# {}\n\n", deck.brief.title);
    for (label, value) in [
        ("受众", &deck.brief.audience),
        ("任务", &deck.brief.task_type),
        ("目标", &deck.brief.goal),
    ] {
        if !value.is_empty() {
            output.push_str(&format!("**{label}**：{value}\n\n"));
        }
    }
    list(&mut output, "约束", &deck.brief.constraints);
    if let Some(limit) = deck.brief.page_limit {
        output.push_str(&format!("\n**页数上限**：{limit}\n"));
    }
    if !deck.framing.thesis.is_empty() {
        output.push_str(&format!("## 主张\n\n{}\n", deck.framing.thesis));
    }
    for pillar in &deck.framing.pillars {
        output.push_str(&format!("\n### {}\n", pillar.title));
        for point in &pillar.points {
            output.push_str(&format!("- {point}\n"));
        }
    }
    list(&mut output, "事实", &deck.framing.facts);
    list(&mut output, "假设", &deck.framing.assumptions);
    list(&mut output, "待回答", &deck.framing.questions);
    for (index, page) in deck.pages.iter().enumerate() {
        output.push_str(&format!("\n## {}. {}\n\n", index + 1, page.content.title));
        if !page.purpose.is_empty() {
            output.push_str(&format!("**本页目的**：{}\n\n", page.purpose));
        }
        if !page.layout.is_empty() {
            output.push_str(&format!("**布局**：{}\n\n", page.layout));
        }
        if !page.content.subtitle.is_empty() {
            output.push_str(&format!("{}\n\n", page.content.subtitle));
        }
        for block in &page.content.body_blocks {
            match block {
                Block::Paragraph { text, .. } => output.push_str(&format!("{text}\n\n")),
                Block::Bullets { heading, items, .. } => {
                    if !heading.is_empty() {
                        output.push_str(&format!("**{heading}**\n\n"));
                    }
                    bullets(&mut output, items, 0);
                    output.push('\n');
                }
                Block::Table {
                    title,
                    columns,
                    rows,
                    ..
                } => {
                    if !title.is_empty() {
                        output.push_str(&format!("**{title}**\n\n"));
                    }
                    if !columns.is_empty() {
                        output.push_str(&format!(
                            "| {} |\n",
                            columns
                                .iter()
                                .map(|c| cell(&c.label))
                                .collect::<Vec<_>>()
                                .join(" | ")
                        ));
                        output
                            .push_str(&format!("| {} |\n", vec!["---"; columns.len()].join(" | ")));
                        for row in rows {
                            let values: Vec<_> = columns
                                .iter()
                                .map(|column| {
                                    row.cells
                                        .iter()
                                        .find(|c| c.column_id == column.id)
                                        .map(|c| cell(&c.display_text))
                                        .unwrap_or_default()
                                })
                                .collect();
                            output.push_str(&format!("| {} |\n", values.join(" | ")));
                        }
                        output.push('\n');
                    }
                }
            }
        }
        for (label, items) in [
            ("标签", &page.content.labels),
            ("补充", &page.content.callouts),
            ("脚注", &page.content.footnotes),
        ] {
            if !items.is_empty() {
                output.push_str(&format!("**{label}**\n\n"));
                bullets(&mut output, items, 0);
            }
        }
        if !page.notes.is_empty() {
            output.push_str(&format!("\n**讲稿**\n\n{}\n", page.notes));
        }
        list(&mut output, "待补", &page.todo);
        list(&mut output, "出处", &page.refs);
    }
    output
}
