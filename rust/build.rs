use std::{env, fs, io, path::Path};

fn embed(root: &Path, directory: &Path, source: &mut String) -> io::Result<()> {
    let mut entries = fs::read_dir(directory)?.collect::<io::Result<Vec<_>>>()?;
    entries.sort_by_key(|entry| entry.file_name());
    for entry in entries {
        let path = entry.path();
        if entry.file_type()?.is_dir() {
            embed(root, &path, source)?;
        } else if entry.file_type()?.is_file() {
            let name = path.strip_prefix(root).map_err(io::Error::other)?;
            let name = name.to_string_lossy().replace('\\', "/");
            source.push_str(&format!(
                "({name:?}, include_bytes!({:?})),\n",
                path.canonicalize()?
            ));
        }
    }
    Ok(())
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Embed the entire built directory so hashed JS/CSS assets survive install.
    let root = Path::new(&env::var("CARGO_MANIFEST_DIR")?).join("web-dist");
    println!("cargo:rerun-if-changed=web-dist");
    let index = root.join("index.html");
    if !index.is_file() {
        return Err(format!(
            "前端首页 {} 不存在或不是文件；请先构建静态资源",
            index.display()
        )
        .into());
    }
    let mut source = String::from("static ASSETS: &[(&str, &[u8])] = &[\n");
    embed(&root, &root, &mut source)?;
    source.push_str("];\n");
    fs::write(Path::new(&env::var("OUT_DIR")?).join("assets.rs"), source)?;
    Ok(())
}
