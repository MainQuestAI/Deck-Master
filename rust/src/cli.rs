use crate::error::Result;
use crate::model::Patch;
use crate::ops;
use clap::{Parser, Subcommand};
use serde::Serialize;
use std::io::Write;
use std::path::PathBuf;

#[derive(Parser)]
#[command(name = "deck", version, about = "创建、修改和导出方案作品")]
struct Cli {
    #[arg(long, global = true, default_value = ".", help = "作品目录")]
    project: PathBuf,
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    #[command(about = "新建不完整作品")]
    New {
        project: PathBuf,
        #[arg(long, default_value = "", help = "作品标题")]
        title: String,
    },
    #[command(about = "添加或读取材料")]
    Material {
        #[command(subcommand)]
        command: MaterialCommand,
    },
    #[command(about = "查看作品摘要和版本历史（JSON）")]
    Show,
    #[command(about = "读取作品正文（JSON）")]
    Get {
        #[arg(long, value_delimiter = ',', help = "只取指定页；省略时取全稿")]
        pages: Option<Vec<String>>,
    },
    #[command(about = "按基线保存改动（JSON）")]
    Put {
        #[arg(long, help = "读取时的版本号")]
        base: i64,
        file: PathBuf,
    },
    #[command(about = "把历史版本恢复为新版本")]
    Restore { version: i64 },
    #[command(about = "导出可读稿")]
    Export {
        #[command(subcommand)]
        command: ExportCommand,
    },
}

#[derive(Subcommand)]
enum MaterialCommand {
    #[command(about = "保存原件并抽取文字")]
    Add { file: PathBuf },
    #[command(about = "返回抽取文本的路径（JSON）")]
    Text { id: String },
}

#[derive(Subcommand)]
enum ExportCommand {
    #[command(about = "输出 Markdown，包括未完成内容")]
    Md,
}

fn print_json(value: impl Serialize) -> Result<()> {
    let stdout = std::io::stdout();
    let mut out = stdout.lock();
    serde_json::to_writer_pretty(&mut out, &value)?;
    writeln!(&mut out)?;
    Ok(())
}

pub fn run() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Commands::New { project, title } => print_json(ops::new(&project, title)?),
        Commands::Show => print_json(ops::show(&cli.project)?),
        Commands::Get { pages } => print_json(ops::get(&cli.project, pages.as_deref())?),
        Commands::Put { base, file } => {
            let mut value: serde_json::Value = serde_json::from_slice(&std::fs::read(file)?)?;
            if let Some(deck) = value.get_mut("deck") {
                value = deck.take();
            }
            let patch: Patch = serde_json::from_value(value)?;
            print_json(ops::put(&cli.project, base, patch)?)
        }
        Commands::Restore { version } => print_json(ops::restore(&cli.project, version)?),
        Commands::Material {
            command: MaterialCommand::Add { file },
        } => print_json(ops::material_add(&cli.project, &file)?),
        Commands::Material {
            command: MaterialCommand::Text { id },
        } => print_json(ops::material_text(&cli.project, &id)?),
        Commands::Export {
            command: ExportCommand::Md,
        } => {
            std::io::stdout()
                .lock()
                .write_all(ops::export_md(&cli.project)?.as_bytes())?;
            Ok(())
        }
    }
}
