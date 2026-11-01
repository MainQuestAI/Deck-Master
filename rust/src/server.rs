use crate::{
    error::{Error, Result},
    model::Patch,
    ops,
};
use serde_json::{Value, json};
use std::{fs::File, io::Write, net::SocketAddr, path::Path};
use tiny_http::{Header, Method, Request, Response, ResponseBox, Server};

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
    let status = match &error {
        Error::Conflict(_) => 409,
        Error::NeedsTool(_) => 503,
        Error::Tool(_) => 500,
        Error::Missing(_) => 404,
        Error::Io(_) | Error::Sql(_) => 500,
        _ => 400,
    };
    let mut value = json!({"error": error.to_string()});
    if status == 409 {
        value["exit_code"] = json!(error.exit_code());
    }
    json_response(status, value)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn io_not_found_is_a_server_error() {
        let temp = tempfile::tempdir().unwrap();
        let error = std::fs::read(temp.path().join("missing-tool-output")).unwrap_err();
        assert_eq!(error_response(error.into()).unwrap().status_code().0, 500);
    }
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
    // JSON in a header must also work for non-ASCII author page IDs.
    let mut ascii = String::new();
    for c in serde_json::to_string(value)?.chars() {
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
    json_response(200, value)
}

fn route(project: &Path, request: &mut Request) -> Result<ResponseBox> {
    let url = request.url().to_owned();
    let (path, query) = url.split_once('?').unwrap_or((&url, ""));
    match (request.method(), path) {
        (Method::Get, "/api/deck") => json_response(200, ops::workspace(project)?),
        (Method::Put, "/api/deck") => {
            let base = query
                .strip_prefix("base=")
                .ok_or_else(|| Error::Input("保存需要 ?base=读取时的版本号".into()))?;
            let base = identifier(base)?;
            let mut data = Vec::new();
            request.as_reader().read_to_end(&mut data)?;
            let submitted: Value = serde_json::from_slice(&data)?;
            let patch: Patch = serde_json::from_value(submitted.clone())?;
            match ops::put(project, base, patch) {
                Ok(snapshot) => json_response(200, serde_json::to_value(snapshot)?),
                Err(Error::Conflict(conflicts)) => json_response(
                    409,
                    json!({
                        "error": "保存冲突；请比较当前内容后重新提交，保留本地输入",
                        "exit_code": 5, "base": base, "submitted": submitted,
                        "conflicts": serde_json::from_str::<Value>(&conflicts)?
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
                    "Content-Security-Policy",
                    "sandbox; default-src 'none'; img-src data:; style-src 'unsafe-inline'",
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
                return Ok(Response::from_data(*bytes)
                    .with_header(header("Content-Type", content_type(name))?)
                    .boxed());
            }
            json_response(404, json!({"error":"文件不存在"}))
        }
        _ => json_response(404, json!({"error":"接口不存在"})),
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
    loop {
        let request = server.recv()?;
        let project = project.clone();
        std::thread::spawn(move || {
            let mut request = request;
            let response = if local_request(&request, address.port()) {
                route(&project, &mut request).or_else(error_response)
            } else {
                json_response(403, json!({"error":"仅接受本服务的本机 Host 与 Origin"}))
            };
            match response.and_then(|mut response| {
                response.add_header(header("Cache-Control", "no-store")?);
                response.add_header(header("X-Content-Type-Options", "nosniff")?);
                request.respond(response).map_err(Error::Io)
            }) {
                Ok(()) => {}
                Err(error) => eprintln!("本地请求失败：{error}"),
            }
        });
    }
}
