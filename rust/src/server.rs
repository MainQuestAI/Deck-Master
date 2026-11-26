use crate::{
    error::{Error, Result},
    ops,
};
use serde_json::{Value, json};
use std::{
    fs::File,
    io::{Read, Write},
    net::SocketAddr,
    path::Path,
    sync::{Arc, Mutex, mpsc},
};
use tiny_http::{Header, Method, Request, Response, ResponseBox, Server};

const MAX_BODY_BYTES: usize = 8 * 1024 * 1024;
const MAX_WORKERS: usize = 16;

fn is_json_content_type(request: &Request) -> bool {
    let mut found = false;
    for header in request.headers() {
        if header.field.equiv("Content-Type") {
            if found {
                return false;
            }
            let media = header.value.as_str().split(';').next().unwrap_or("").trim();
            if !media.eq_ignore_ascii_case("application/json") {
                return false;
            }
            found = true;
        }
    }
    found
}

fn read_body_limited(request: &mut Request) -> Result<std::result::Result<Vec<u8>, ResponseBox>> {
    if request
        .body_length()
        .is_some_and(|len| len > MAX_BODY_BYTES)
    {
        return Ok(Err(json_response(
            413,
            json!({"error":"请求体超过 8 MiB 上限"}),
        )?));
    }
    let mut body = Vec::new();
    request
        .as_reader()
        .take((MAX_BODY_BYTES + 1) as u64)
        .read_to_end(&mut body)?;
    if body.len() > MAX_BODY_BYTES {
        return Ok(Err(json_response(
            413,
            json!({"error":"请求体超过 8 MiB 上限"}),
        )?));
    }
    Ok(Ok(body))
}

include!(concat!(env!("OUT_DIR"), "/assets.rs"));

fn header(name: &str, value: &str) -> Result<Header> {
    Header::from_bytes(name, value).map_err(|_| Error::Input("响应头格式有误".into()))
}

fn json_response(status: u16, value: Value) -> Result<ResponseBox> {
    Ok(Response::from_data(serde_json::to_vec(&value)?)
        .with_status_code(status)
        .with_header(header("Content-Type", "application/json; charset=utf-8")?)
        .boxed())
}

fn error_response(error: Error) -> Result<ResponseBox> {
    let status = error.http_status();
    json_response(status, error.to_json(Some("http"), true))
}

fn local_authority(authority: &str, port: u16) -> bool {
    let Some((host, supplied_port)) = authority.rsplit_once(':') else {
        return false;
    };
    (host.eq_ignore_ascii_case("localhost") || host == "127.0.0.1")
        && supplied_port.parse::<u16>() == Ok(port)
}

fn local_request(request: &Request, port: u16) -> bool {
    let hosts: Vec<_> = request
        .headers()
        .iter()
        .filter(|h| h.field.equiv("Host"))
        .collect();
    let origins: Vec<_> = request
        .headers()
        .iter()
        .filter(|h| h.field.equiv("Origin"))
        .collect();
    hosts.len() == 1
        && local_authority(hosts[0].value.as_str(), port)
        && origins.len() <= 1
        && origins.iter().all(|h| {
            h.value
                .as_str()
                .strip_prefix("http://")
                .is_some_and(|authority| local_authority(authority, port))
        })
}

fn content_type(path: &str) -> &'static str {
    match path.rsplit('.').next().unwrap_or("") {
        "html" => "text/html; charset=utf-8",
        "js" | "mjs" => "text/javascript; charset=utf-8",
        "css" => "text/css; charset=utf-8",
        "json" | "map" => "application/json",
        "svg" => "image/svg+xml",
        "png" => "image/png",
        "jpg" | "jpeg" => "image/jpeg",
        "ico" => "image/x-icon",
        "woff" => "font/woff",
        "woff2" => "font/woff2",
        "md" => "text/markdown; charset=utf-8",
        "pptx" => "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        _ => "application/octet-stream",
    }
}

fn status_header(value: &Value) -> Result<Header> {
    // Reports, notes and findings belong in the body, never in a download header.
    let keys = [
        "id",
        "url",
        "version_id",
        "input_changed",
        "warning",
        "build_missing_pages",
        "missing_pages",
        "stale_pages",
        "stale_images",
        "warnings",
        "incomplete_basis_pages",
        "content_review",
        "current_content_review",
    ];
    let value: serde_json::Map<String, Value> = keys
        .into_iter()
        .filter_map(|key| value.get(key).map(|value| (key.to_owned(), value.clone())))
        .collect();
    // JSON in a header must also work for non-ASCII author page IDs.
    let mut ascii = String::new();
    for c in serde_json::to_string(&value)?.chars() {
        if c.is_ascii() {
            ascii.push(c);
        } else {
            for unit in c.encode_utf16(&mut [0; 2]) {
                ascii.push_str(&format!("\\u{unit:04x}"));
            }
        }
    }
    header("X-Deck-Status", &ascii)
}

fn identifier(text: &str) -> Result<i64> {
    text.parse::<i64>()
        .ok()
        .filter(|id| *id > 0)
        .ok_or_else(|| Error::Input("编号必须是正整数".into()))
}

fn url_component(text: &str) -> Result<String> {
    let mut bytes = Vec::new();
    let mut input = text.bytes();
    while let Some(byte) = input.next() {
        match byte {
            b'%' => {
                let high = input.next().and_then(|b| char::from(b).to_digit(16));
                let low = input.next().and_then(|b| char::from(b).to_digit(16));
                let (Some(high), Some(low)) = (high, low) else {
                    return Err(Error::Input("URL 编码有误".into()));
                };
                bytes.push((high * 16 + low) as u8);
            }
            _ => bytes.push(byte),
        }
    }
    String::from_utf8(bytes).map_err(|_| Error::Input("URL 必须使用 UTF-8".into()))
}

#[derive(serde::Deserialize)]
struct ReviewInput {
    page_id: Option<String>,
    text: String,
    reviewer: Option<String>,
}

fn build_response(project: &Path) -> Result<ResponseBox> {
    let mut value = ops::build(project)?;
    let path = value["path"]
        .as_str()
        .ok_or_else(|| Error::Tool("构建缺少文件路径".into()))?;
    let name = Path::new(path)
        .file_name()
        .and_then(|n| n.to_str())
        .ok_or_else(|| Error::Tool("构建文件名有误".into()))?;
    let sha = name.split('.').next().unwrap_or("").to_owned();
    value.as_object_mut().map(|o| o.remove("path"));
    value["url"] = json!(format!("/api/files/{sha}"));
    Ok(Response::from_data(serde_json::to_vec(&value)?)
        .with_status_code(200)
        .with_header(header("Content-Type", "application/json; charset=utf-8")?)
        .with_header(status_header(&value)?)
        .boxed())
}

fn route(project: &Path, request: &mut Request) -> Result<ResponseBox> {
    let url = request.url().to_owned();
    let (path, query) = url.split_once('?').unwrap_or((&url, ""));
    match (request.method(), path) {
        (Method::Get, "/api/reviews") => {
            let mut status = None;
            let mut page = None;
            let mut record = None;
            for pair in query.split('&').filter(|p| !p.is_empty()) {
                let (key, value) = pair.split_once('=').unwrap_or((pair, ""));
                let value = url_component(&value.replace('+', " "))?;
                match key {
                    "status" => status = Some(value),
                    "page" => page = Some(value),
                    "record" => record = Some(value),
                    _ => return Err(Error::Input("审阅查询只接受 status、page 和 record".into())),
                }
            }
            json_response(
                200,
                ops::review_list_records(
                    project,
                    status.as_deref(),
                    page.as_deref(),
                    record.as_deref().unwrap_or("comment"),
                )?,
            )
        }
        (Method::Get, path) if path.starts_with("/api/reviews/") => {
            let id = identifier(&path[13..])?;
            json_response(200, serde_json::to_value(ops::review_get(project, id)?)?)
        }
        (Method::Post, "/api/reviews") => {
            let body = match read_body_limited(request)? {
                Ok(body) => body,
                Err(response) => return Ok(response),
            };
            if !body.is_empty() && !is_json_content_type(request) {
                return json_response(
                    415,
                    json!({"error":"请求头 Content-Type 必须为 application/json"}),
                );
            }
            let input: ReviewInput = serde_json::from_slice(&body)?;
            json_response(
                200,
                serde_json::to_value(ops::review_add(
                    project,
                    input.page_id.as_deref(),
                    &input.text,
                    input.reviewer.as_deref().unwrap_or("author"),
                    "human",
                )?)?,
            )
        }
        (Method::Post, path) if path.starts_with("/api/reviews/") && path.ends_with("/resolve") => {
            let text = path
                .strip_prefix("/api/reviews/")
                .and_then(|p| p.strip_suffix("/resolve"))
                .ok_or_else(|| Error::Input("处理意见需要意见编号".into()))?;
            let id = identifier(text)?;
            json_response(
                200,
                serde_json::to_value(ops::review_resolve(project, id)?)?,
            )
        }
        (Method::Post, path) if path.starts_with("/api/runs/") && path.contains("/adopt/") => {
            let (run, page) = path[10..]
                .split_once("/adopt/")
                .ok_or_else(|| Error::Input("采用结果需要 run 和页面编号".into()))?;
            #[derive(Default, serde::Deserialize)]
            #[serde(deny_unknown_fields)]
            struct AdoptInput {
                expected_file: Option<String>,
            }
            let body = match read_body_limited(request)? {
                Ok(body) => body,
                Err(response) => return Ok(response),
            };
            if !body.is_empty() && !is_json_content_type(request) {
                return json_response(
                    415,
                    json!({"error":"请求头 Content-Type 必须为 application/json"}),
                );
            }
            let input: AdoptInput = if body.is_empty() {
                AdoptInput::default()
            } else {
                serde_json::from_slice(&body)?
            };
            let mut result = ops::run_adopt_candidate(
                project,
                identifier(run)?,
                &url_component(page)?,
                input.expected_file.as_deref(),
            )?;
            for page in result["runs"][0]["pages"]
                .as_array_mut()
                .into_iter()
                .flatten()
            {
                if let Some(page) = page.as_object_mut() {
                    page.remove("findings_path");
                    page.remove("work");
                }
            }
            json_response(200, result)
        }
        (Method::Get, path) if path.starts_with("/api/builds/") => {
            json_response(200, ops::build_detail(project, identifier(&path[12..])?)?)
        }
        (Method::Get, "/api/deck") => {
            let mut ws_query = ops::WorkspaceQuery::default();
            for pair in query.split('&').filter(|p| !p.is_empty()) {
                let (key, value) = pair.split_once('=').unwrap_or((pair, ""));
                let parsed = identifier(value)? as usize;
                let clamped = parsed.min(500);
                match key {
                    "runs_limit" => ws_query.runs_limit = clamped,
                    "history_limit" => ws_query.history_limit = clamped,
                    _ => {
                        return Err(Error::Input(
                            "工作区查询只接受 runs_limit 和 history_limit".into(),
                        ));
                    }
                }
            }
            let if_none_match = request
                .headers()
                .iter()
                .find(|h| h.field.equiv("If-None-Match"))
                .map(|h| h.value.as_str());
            let (etag, snapshot) = ops::workspace_with_etag(project, ws_query, if_none_match)?;
            match snapshot {
                None => Ok(Response::empty(304)
                    .with_header(header("ETag", &etag)?)
                    .with_header(header("Cache-Control", "no-cache")?)
                    .boxed()),
                Some(body) => Ok(Response::from_data(serde_json::to_vec(&body)?)
                    .with_status_code(200)
                    .with_header(header("Content-Type", "application/json; charset=utf-8")?)
                    .with_header(header("ETag", &etag)?)
                    .with_header(header("Cache-Control", "no-cache")?)
                    .boxed()),
            }
        }
        (Method::Get, path) if path.starts_with("/api/versions/") => {
            let version = identifier(&path[14..])?;
            json_response(
                200,
                serde_json::to_value(ops::version_get(project, version)?)?,
            )
        }
        (Method::Put, "/api/deck") => {
            let base = query
                .strip_prefix("base=")
                .ok_or_else(|| Error::Input("保存需要 ?base=读取时的版本号".into()))?;
            let base = identifier(base)?;
            let data = match read_body_limited(request)? {
                Ok(data) => data,
                Err(response) => return Ok(response),
            };
            if !is_json_content_type(request) {
                return json_response(
                    415,
                    json!({"error":"请求头 Content-Type 必须为 application/json"}),
                );
            }
            let submitted: Value = serde_json::from_slice(&data)?;
            let patch = crate::ops::put_patch(submitted.clone(), false)?;
            match ops::put(project, base, patch) {
                Ok(snapshot) => json_response(200, serde_json::to_value(snapshot)?),
                Err(Error::Conflict { items, .. }) => json_response(
                    409,
                    json!({
                        "code": "conflict",
                        "exit_code": 5,
                        "step": "put",
                        "message": "保存冲突；请比较当前内容后重新提交，保留本地输入",
                        "next": "请读取当前最新内容、解决冲突后重新提交",
                        "error": "保存冲突；请比较当前内容后重新提交，保留本地输入",
                        "base": base,
                        "submitted": submitted,
                        "conflicts": items,
                    }),
                ),
                Err(error) => Err(error),
            }
        }
        (Method::Post, "/api/build") => build_response(project),
        (Method::Get, "/api/export/md") => {
            let (markdown, status) = ops::export_markdown(project)?;
            Ok(Response::from_string(markdown)
                .with_header(header("Content-Type", content_type("deck.md"))?)
                .with_header(header(
                    "Content-Disposition",
                    "attachment; filename=deck.md",
                )?)
                .with_header(status_header(&status)?)
                .boxed())
        }
        (Method::Get, "/api/export/pptx") => {
            let mut value = ops::export_pptx(project)?;
            let path = value["path"]
                .as_str()
                .ok_or_else(|| Error::Tool("导出缺少文件路径".into()))?;
            let file = File::open(path)?;
            value.as_object_mut().map(|o| o.remove("path"));
            Ok(Response::from_file(file)
                .with_header(header("Content-Type", content_type("deck.pptx"))?)
                .with_header(header(
                    "Content-Disposition",
                    "attachment; filename=deck.pptx",
                )?)
                .with_header(status_header(&value)?)
                .boxed())
        }
        (Method::Get, path) if path.starts_with("/api/files/") => {
            let file = ops::project_file(project, &path[11..])?;
            Ok(Response::from_file(File::open(&file)?)
                .with_header(header(
                    "Content-Type",
                    content_type(file.to_str().unwrap_or("")),
                )?)
                .with_header(header(
                    "Cache-Control",
                    "private, max-age=31536000, immutable",
                )?)
                .with_header(header(
                    "Content-Security-Policy",
                    "sandbox; default-src 'none'; img-src data:; style-src 'unsafe-inline'; frame-ancestors 'none'",
                )?)
                .boxed())
        }
        (Method::Post, path) if path.starts_with("/api/restore/") => json_response(
            200,
            serde_json::to_value(ops::restore(project, identifier(&path[13..])?)?)?,
        ),
        (Method::Post, path) if path.starts_with("/api/runs/") && path.ends_with("/cancel") => {
            let text = path
                .strip_prefix("/api/runs/")
                .and_then(|p| p.strip_suffix("/cancel"))
                .ok_or_else(|| Error::Input("停止任务需要 run 编号".into()))?;
            let id = identifier(text)?;
            json_response(200, ops::run_cancel(project, id)?)
        }
        (Method::Get, path) if !path.starts_with("/api/") => {
            let name = if path == "/" {
                "index.html"
            } else {
                path.trim_start_matches('/')
            };
            if let Some((_, bytes)) = ASSETS.iter().find(|(key, _)| *key == name) {
                let mut response = Response::from_data(*bytes)
                    .with_header(header("Content-Type", content_type(name))?);
                if name.ends_with(".html") {
                    response = response.with_header(header(
                        "Content-Security-Policy",
                        "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'",
                    )?);
                }
                return Ok(response.boxed());
            }
            json_response(404, json!({"error":"文件不存在"}))
        }
        _ => json_response(404, json!({"error":"接口不存在"})),
    }
}

fn handle_request(project: &Path, port: u16, mut request: Request) {
    let response = if local_request(&request, port) {
        route(project, &mut request).or_else(error_response)
    } else {
        json_response(403, json!({"error":"仅接受本服务的本机 Host 与 Origin"}))
    };
    match response.and_then(|mut response| {
        if !response
            .headers()
            .iter()
            .any(|item| item.field.equiv("Cache-Control"))
        {
            response.add_header(header("Cache-Control", "no-store")?);
        }
        response.add_header(header("X-Content-Type-Options", "nosniff")?);
        response.add_header(header("X-Frame-Options", "DENY")?);
        if !response
            .headers()
            .iter()
            .any(|item| item.field.equiv("Content-Security-Policy"))
        {
            response.add_header(header("Content-Security-Policy", "frame-ancestors 'none'")?);
        }
        request.respond(response).map_err(Error::Io)
    }) {
        Ok(()) => {}
        Err(error) => eprintln!("本地请求失败：{error}"),
    }
}

pub fn serve(project: &Path) -> Result<()> {
    let project = project.canonicalize()?;
    ops::get(&project, None)?;
    let server = Server::http("127.0.0.1:0")
        .map_err(|e| Error::Input(format!("无法启动本地服务：{e}；请检查网络权限")))?;
    let address: SocketAddr = server
        .server_addr()
        .to_ip()
        .ok_or_else(|| Error::Input("无法取得本地监听地址".into()))?;
    println!("http://{address}");
    std::io::stdout().flush()?;
    let (sender, receiver) = mpsc::channel::<Request>();
    let receiver = Arc::new(Mutex::new(receiver));
    for _ in 0..MAX_WORKERS {
        let rx = Arc::clone(&receiver);
        let project = project.clone();
        let port = address.port();
        std::thread::spawn(move || {
            loop {
                let request = match rx.lock() {
                    Ok(guard) => match guard.recv() {
                        Ok(request) => request,
                        Err(_) => break,
                    },
                    Err(_) => break,
                };
                handle_request(&project, port, request);
            }
        });
    }
    loop {
        match server.recv() {
            Ok(request) => {
                if sender.send(request).is_err() {
                    break;
                }
            }
            Err(error) => {
                eprintln!("接收本机连接失败：{error}");
            }
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn historical_version_route_uses_saved_content_and_existing_error_mapping() {
        let temp = tempfile::tempdir().unwrap();
        let path = temp.path();
        let saved = ops::new(path, "历史标题".into()).unwrap();
        ops::put(
            path,
            saved.version,
            serde_json::from_value(json!({"brief":{"title":"当前标题"}})).unwrap(),
        )
        .unwrap();
        for (method, url, expected_status) in [
            (Method::Get, "/api/versions/1", 200),
            (Method::Get, "/api/versions/99", 404),
            (Method::Get, "/api/versions/0", 400),
            (Method::Get, "/api/versions/-1", 400),
            (Method::Get, "/api/versions/invalid", 400),
            (Method::Get, "/api/versions/9223372036854775808", 400),
            (Method::Put, "/api/deck?base=99", 400),
            (Method::Post, "/api/restore/99", 400),
        ] {
            let is_write = matches!(method, Method::Put | Method::Post);
            let mut builder = tiny_http::TestRequest::new()
                .with_method(method)
                .with_path(url)
                .with_body("{}");
            if is_write {
                builder = builder.with_header(header("Content-Type", "application/json").unwrap());
            }
            let mut request = builder.into();
            let response = route(path, &mut request).or_else(error_response).unwrap();
            assert_eq!(response.status_code().0, expected_status, "{url}");
            let body: Value = serde_json::from_reader(response.into_reader()).unwrap();
            if expected_status == 200 {
                assert_eq!(body, serde_json::to_value(&saved).unwrap());
            } else {
                assert!(body["error"].is_string());
                assert!(body.get("deck").is_none());
            }
        }
    }

    #[test]
    fn io_not_found_is_a_server_error() {
        let temp = tempfile::tempdir().unwrap();
        let error = std::fs::read(temp.path().join("missing-tool-output")).unwrap_err();
        assert_eq!(error_response(error.into()).unwrap().status_code().0, 500);
    }
}
