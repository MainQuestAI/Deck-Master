use crate::error::{Error, ErrorFormat, Result};
use crate::ops;
use clap::{CommandFactory, FromArgMatches, Parser, Subcommand, parser::ValueSource};
use serde::Serialize;
use std::io::Write;
use std::path::PathBuf;

#[derive(Parser)]
#[command(name = "deck", version, about = "创建、修改和导出方案作品")]
struct Cli {
    #[arg(long, global = true, default_value = ".", help = "作品目录")]
    project: PathBuf,
    #[arg(
        long,
        global = true,
        default_value = "text",
        value_parser = ["text", "json"],
        value_name = "text|json",
        help = "错误输出格式：text（默认）或 json（结构化 JSON 到 stderr）"
    )]
    error_format: String,
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    #[command(about = "添加、读取和处理页上或整稿意见")]
    Review {
        #[command(subcommand)]
        command: ReviewCommand,
    },
    #[command(about = "在本机浏览、修改和下载作品")]
    Serve {
        #[arg(value_name = "PROJECT", help = "作品目录（省略时使用 --project）")]
        directory: Option<PathBuf>,
    },
    #[command(about = "选择图片素材")]
    Asset {
        #[command(subcommand)]
        command: AssetCommand,
    },
    #[command(about = "管理作品视觉风格与母版主题")]
    Style {
        #[command(subcommand)]
        command: StyleCommand,
    },
    #[command(about = "准备、停止和交回 Host 任务")]
    Run {
        #[command(subcommand)]
        command: RunCommand,
    },
    #[command(about = "检索内置 Tabler 图标")]
    Icon {
        #[command(subcommand)]
        command: IconCommand,
    },
    #[command(
        about = "将已采用的页面构建为可编辑 PPTX。stale_pages 是页面依据已变；stale_images 是原图依据已变。warnings 里的 stale_image 与 shared_layout 都不阻断"
    )]
    Build,
    #[command(about = "检查解释器、rsvg-convert、soffice、pdftoppm、fc-match；未指定字体时只警告")]
    Doctor {
        #[arg(
            long,
            value_delimiter = ',',
            help = "要检查的字体名；省略时只警告未检查字体"
        )]
        fonts: Vec<String>,
    },
    #[command(about = "新建不完整作品")]
    New {
        #[arg(value_name = "PROJECT", help = "新建作品目录（省略时使用 --project）")]
        project: Option<PathBuf>,
        #[arg(long, default_value = "", help = "作品标题")]
        title: String,
    },
    #[command(about = "从旧项目导出档案创建新作品")]
    Import {
        #[arg(value_name = "OUT")]
        source: PathBuf,
        #[arg(value_name = "NEW")]
        destination: PathBuf,
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
enum ReviewCommand {
    #[command(about = "记录意见或出稿审稿；不修改作品版本")]
    Add {
        text: Option<String>,
        #[arg(long)]
        page: Option<String>,
        #[arg(
            long,
            value_parser = ["self_check", "other_model", "human"],
            value_name = "self_check|other_model|human",
            help = "审阅方式（必填）：self_check、other_model、human"
        )]
        method: String,
        #[arg(long, default_value = "author")]
        reviewer: String,
        #[arg(
            long,
            default_value = "comment",
            value_parser = ["comment", "content_review"],
            help = "comment 是意见；content_review 是整稿出稿审稿"
        )]
        record: String,
        #[arg(long, help = "出稿审稿的六项检查 JSON")]
        checks: Option<PathBuf>,
    },
    #[command(about = "按类型、状态或页面读取审阅记录")]
    List {
        #[arg(
            long,
            value_parser = ["open", "resolved"],
            value_name = "open|resolved",
            help = "按状态筛选：open 或 resolved"
        )]
        status: Option<String>,
        #[arg(long, help = "按页面 ID 筛选")]
        page: Option<String>,
        #[arg(
            long,
            default_value = "comment",
            value_parser = ["comment", "content_review", "all"],
            help = "记录类型：comment、content_review 或 all"
        )]
        record: String,
    },
    #[command(about = "按编号读取完整审阅记录")]
    Get { id: i64 },
    #[command(about = "标记意见已处理")]
    Resolve { id: i64 },
}

#[derive(Subcommand)]
enum MaterialCommand {
    #[command(about = "保存原件并抽取文字")]
    Add { file: PathBuf },
    #[command(about = "返回抽取文本及保存原件的路径（JSON）")]
    Text { id: String },
}

#[derive(Subcommand)]
enum AssetCommand {
    #[command(about = "添加素材；同 ID 替换当前选择，原文件保留")]
    Add {
        id: String,
        file: PathBuf,
        #[arg(
            long = "page",
            help = "只供指定页使用；可重复或逗号分隔，省略则为公共素材"
        )]
        pages: Vec<String>,
        #[arg(long, default_value = "", help = "所选素材的来源")]
        source: String,
        #[arg(long, default_value = "", help = "所选素材的许可")]
        license: String,
    },
}

#[derive(Subcommand)]
enum StyleCommand {
    #[command(about = "设置或清除企业 PPTX 母版主题")]
    Theme {
        #[command(subcommand)]
        command: ThemeCommand,
    },
}

#[derive(Subcommand)]
enum ThemeCommand {
    #[command(about = "清洗并导入企业 PPTX 模板作为输出母版（仅保留母版、版式和主题）")]
    Set { file: PathBuf },
    #[command(about = "清除已配置的母版主题，恢复默认 16:9 空白母版")]
    Clear,
}

#[derive(Subcommand)]
enum IconCommand {
    #[command(about = "按中文或英文关键词检索内置 Tabler 图标")]
    Search {
        query: String,
        #[arg(long, default_value_t = 12, help = "最多返回的图标数量（1-100）")]
        limit: usize,
    },
}

#[derive(Subcommand)]
enum RunCommand {
    #[command(about = "准备指定页的生图、SVG 或 native 任务")]
    Start {
        #[arg(
            value_parser = ["image", "svg", "native"],
            value_name = "image|svg|native",
            help = "任务类型：image、svg 或 native"
        )]
        kind: String,
        #[arg(
            long,
            value_delimiter = ',',
            required = true,
            help = "目标页面 ID（逗号分隔）"
        )]
        pages: Vec<String>,
        #[arg(long, help = "仅 image 可设：最大外部调用次数")]
        max_calls: Option<i64>,
    },
    #[command(about = "生图前登记一次外部调用")]
    Call {
        run: i64,
        page: String,
        #[arg(long)]
        retry: bool,
    },
    #[command(about = "交回生成文件；取消或依据变化时仅保存")]
    Result {
        run: i64,
        page: String,
        file: PathBuf,
    },
    #[command(about = "停止后续调用和自动采用")]
    Cancel { run: i64 },
    #[command(about = "读取任务状态与工作目录")]
    Show { run: Option<i64> },
    #[command(about = "手动采用已保存结果")]
    Adopt {
        run: i64,
        page: String,
        #[arg(
            long,
            help = "native 必填：本页对照结论。只剩确认用语时仍采用，并提示 note_unspecific"
        )]
        note: Option<String>,
    },
    #[command(about = "从 native 页面原图裁剪局部图并保存到当前页面工作目录")]
    Crop {
        run: i64,
        page: String,
        #[arg(long, value_name = "x,y,w,h", help = "原图像素坐标框：x,y,w,h")]
        bbox: String,
        #[arg(long, help = "输出素材名（保存为 assets/<name>.png）")]
        name: String,
    },
    #[command(about = "校验 native plan.json，不提交结果也不修改数据库")]
    Validate {
        run: i64,
        page: String,
        file: PathBuf,
    },
}

#[derive(Subcommand)]
enum ExportCommand {
    #[command(
        about = "优先下载当前输入匹配的 PPTX；无匹配时下载最近可用历史成品。stale_pages 是页面依据已变；stale_images 是原图依据已变。warnings 里的 stale_image 与 shared_layout 都不阻断"
    )]
    Pptx,
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

fn requested_json_errors() -> bool {
    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        if arg == "--error-format" && args.next().as_deref() == Some("json") {
            return true;
        }
        if arg == "--error-format=json" {
            return true;
        }
    }
    false
}

pub fn execute() -> i32 {
    let json_hint = requested_json_errors();
    let command = Cli::command();
    let matches = match command.try_get_matches() {
        Ok(matches) => matches,
        Err(error) => {
            if json_hint && error.exit_code() != 0 {
                let err = Error::Input(error.to_string().trim().to_string());
                eprintln!(
                    "{}",
                    serde_json::to_string_pretty(&err.to_json(Some("cli"), false))
                        .unwrap_or_else(|_| err.to_string())
                );
                return err.exit_code();
            }
            error.exit();
        }
    };
    let project_explicit = matches.value_source("project") == Some(ValueSource::CommandLine);
    let step = matches.subcommand_name().map(str::to_string);
    let cli = Cli::from_arg_matches(&matches).unwrap_or_else(|error| error.exit());
    let format = if cli.error_format == "json" {
        ErrorFormat::Json
    } else {
        ErrorFormat::Text
    };
    if let Err(error) = dispatch(cli, project_explicit) {
        match format {
            ErrorFormat::Text => eprintln!("{error}"),
            ErrorFormat::Json => {
                eprintln!(
                    "{}",
                    serde_json::to_string_pretty(&error.to_json(step.as_deref(), false))
                        .unwrap_or_else(|_| error.to_string())
                );
            }
        }
        return error.exit_code();
    }
    0
}

pub fn run() -> Result<()> {
    let matches = Cli::command().get_matches();
    let project_explicit = matches.value_source("project") == Some(ValueSource::CommandLine);
    let cli = Cli::from_arg_matches(&matches).unwrap_or_else(|error| error.exit());
    dispatch(cli, project_explicit)
}

fn dispatch(cli: Cli, project_explicit: bool) -> Result<()> {
    match cli.command {
        Commands::Review { command } => match command {
            ReviewCommand::Add {
                text,
                page,
                method,
                reviewer,
                record,
                checks,
            } => {
                if record == "content_review" {
                    if page.is_some() {
                        return Err(Error::Input(
                            "出稿审稿是整稿一条，不能用 --page 指定页面".into(),
                        ));
                    }
                    let Some(checks) = checks else {
                        return Err(Error::Input(
                            "出稿审稿需要 --checks 指向六项检查的 JSON 文件".into(),
                        ));
                    };
                    print_json(ops::review_add_content(
                        &cli.project,
                        text.as_deref().unwrap_or(""),
                        &reviewer,
                        &method,
                        &checks,
                    )?)
                } else if checks.is_some() {
                    Err(Error::Input(
                        "--checks 只用于出稿审稿（--record content_review）".into(),
                    ))
                } else {
                    print_json(ops::review_add(
                        &cli.project,
                        page.as_deref(),
                        text.as_deref().unwrap_or(""),
                        &reviewer,
                        &method,
                    )?)
                }
            }
            ReviewCommand::List {
                status,
                page,
                record,
            } => print_json(ops::review_list_records(
                &cli.project,
                status.as_deref(),
                page.as_deref(),
                &record,
            )?),
            ReviewCommand::Get { id } => print_json(ops::review_get(&cli.project, id)?),
            ReviewCommand::Resolve { id } => print_json(ops::review_resolve(&cli.project, id)?),
        },
        Commands::Serve { directory } => {
            if directory.is_some() && project_explicit {
                return Err(Error::Input(
                    "serve 不能同时指定位置参数目录与 --project；请只传其中之一".into(),
                ));
            }
            let target = directory.unwrap_or(cli.project);
            crate::server::serve(&target)
        }
        Commands::Build => print_json(ops::build(&cli.project)?),
        Commands::Doctor { fonts } => {
            let result = ops::doctor(&fonts)?;
            print_json(&result)?;
            if result["status"] == "needs_tool" {
                return Err(crate::error::Error::NeedsTool(
                    "生产环境缺少工具或字体；请按检查结果安装后重试".into(),
                ));
            }
            Ok(())
        }
        Commands::Asset {
            command:
                AssetCommand::Add {
                    id,
                    file,
                    pages,
                    source,
                    license,
                },
        } => print_json(ops::asset_add(
            &cli.project,
            &id,
            &file,
            &pages,
            &source,
            &license,
        )?),
        Commands::Run { command } => print_json(match command {
            RunCommand::Start {
                kind,
                pages,
                max_calls,
            } => ops::run_start(&cli.project, &kind, &pages, max_calls)?,
            RunCommand::Call { run, page, retry } => {
                ops::run_call(&cli.project, run, &page, retry)?
            }
            RunCommand::Result { run, page, file } => {
                ops::run_result(&cli.project, run, &page, &file)?
            }
            RunCommand::Cancel { run } => ops::run_cancel(&cli.project, run)?,
            RunCommand::Show { run } => ops::run_show(&cli.project, run)?,
            RunCommand::Adopt { run, page, note } => {
                ops::run_adopt_with_note(&cli.project, run, &page, note.as_deref())?
            }
            RunCommand::Crop {
                run,
                page,
                bbox,
                name,
            } => ops::run_crop(&cli.project, run, &page, &bbox, &name)?,
            RunCommand::Validate { run, page, file } => {
                ops::run_validate(&cli.project, run, &page, &file)?
            }
        }),
        Commands::Icon {
            command: IconCommand::Search { query, limit },
        } => print_json(ops::icon_search(&query, limit)?),
        Commands::Style {
            command: StyleCommand::Theme { command },
        } => print_json(match command {
            ThemeCommand::Set { file } => ops::style_theme_set(&cli.project, &file)?,
            ThemeCommand::Clear => ops::style_theme_clear(&cli.project)?,
        }),
        Commands::Export {
            command: ExportCommand::Pptx,
        } => print_json(ops::export_pptx(&cli.project)?),
        Commands::New { project, title } => {
            let target = project.unwrap_or(cli.project);
            print_json(ops::new(&target, title)?)
        }
        Commands::Import {
            source,
            destination,
        } => print_json(ops::import(&source, &destination)?),
        Commands::Show => print_json(ops::show(&cli.project)?),
        Commands::Get { pages } => print_json(ops::get(&cli.project, pages.as_deref())?),
        Commands::Put { base, file } => {
            let value: serde_json::Value = serde_json::from_slice(&std::fs::read(file)?)?;
            let patch = ops::put_patch(value, true)?;
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
