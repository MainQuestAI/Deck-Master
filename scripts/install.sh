#!/usr/bin/env bash
# Install the Rust CLI, a dedicated deck-tools venv, and Codex skill links.
# The default builds from this checkout. Published GitHub Releases do not yet
# ship prebuilt assets, so a download is opt-in via --archive or --version.
# Both modes prepare a complete component group before switching current.
set -Eeuo pipefail

usage() {
  cat <<'EOF'
用法：install.sh [--prefix DIR] [--skills-root DIR] [--version TAG] [--archive PATH|URL] [--sha256 PATH|HEX] [--from-source] [--dry-run]

安装 deck、独立的 deck-tools 环境和四个 Codex 职责入口。

  --prefix DIR          CLI 安装根目录（默认 ~/.local）
  --skills-root DIR     技能根目录（默认 ~/.codex/skills）
  --version TAG         改为下载该标签的预编译包（当前公开 Release 还没有附件）
  --archive PATH|URL    使用指定的预编译压缩包（本地路径或 https URL）
  --sha256 PATH|HEX     预编译压缩包的 SHA-256 校验文件或 64 位摘要
  --from-source         从本地源码编译安装（需要 cargo 与 npm；这也是默认行为）
  --dry-run             打印计划并检查路径，不写入

默认与 --from-source 相同，从本仓库源码编译，需要 Rust 与 Node。
公开的 GitHub Release 还没有预编译附件，所以默认不会下载。
已有压缩包时用 --archive；远程 URL 必须同时提供 --sha256，本地文件可以省略。
--version 会尝试下载该标签的预编译包。下载失败时请改回 --from-source。
默认将 deck-master、deck-content、deck-design、deck-review 整个目录
软链接到 ~/.codex/skills；--skills-root 更换目录。不再安装兼容入口 deck。
EOF
}

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
prefix="${HOME}/.local"
skills_root="${HOME}/.codex/skills"
mode="${DECK_INSTALL_MODE:-source}"
release_repo="${DECK_RELEASE_REPO:-MainQuestAI/Deck-Master}"
release_tag="${DECK_INSTALL_VERSION:-}"
archive_spec=""
sha256_spec=""
dry_run=0

while [ $# -gt 0 ]; do
  case "$1" in
    --prefix)
      [ $# -ge 2 ] || { echo "install.sh: --prefix 需要目录" >&2; exit 2; }
      prefix=$2
      shift 2
      ;;
    --skill-dir)
      echo "install.sh: --skill-dir 已取消；请用 --skills-root 指定四个职责入口的安装目录" >&2
      exit 2
      ;;
    --skills-root)
      [ $# -ge 2 ] || { echo "install.sh: --skills-root 需要目录" >&2; exit 2; }
      skills_root=$2
      shift 2
      ;;
    --from-source)
      mode=source
      shift
      ;;
    --version)
      [ $# -ge 2 ] || { echo "install.sh: --version 需要发布标签（如 v2.0.0）" >&2; exit 2; }
      release_tag=$2
      mode=prebuilt
      shift 2
      ;;
    --archive)
      [ $# -ge 2 ] || { echo "install.sh: --archive 需要本地路径或 URL" >&2; exit 2; }
      archive_spec=$2
      mode=prebuilt
      shift 2
      ;;
    --sha256)
      [ $# -ge 2 ] || { echo "install.sh: --sha256 需要校验文件或 64 位 SHA-256 摘要" >&2; exit 2; }
      sha256_spec=$2
      shift 2
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "install.sh: 未知参数 $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

[ -n "$skills_root" ] || { echo "install.sh: --skills-root 需要目录" >&2; exit 2; }
while [ "$skills_root" != / ] && [ "${skills_root%/}" != "$skills_root" ]; do
  skills_root=${skills_root%/}
done
[ -n "$prefix" ] || { echo "install.sh: --prefix 需要目录" >&2; exit 2; }
case "$prefix" in /*) ;; *) prefix="$PWD/$prefix" ;; esac
case "$skills_root" in /*) ;; *) skills_root="$PWD/$skills_root" ;; esac
while [ "$prefix" != / ] && [ "${prefix%/}" != "$prefix" ]; do prefix=${prefix%/}; done

detect_target() {
  local os arch
  os=$(uname -s)
  arch=$(uname -m)
  case "${os}:${arch}" in
    Darwin:arm64) printf 'darwin-arm64\n' ;;
    Linux:x86_64|Linux:amd64) printf 'linux-x86_64\n' ;;
    *) return 1 ;;
  esac
}

skill_target="${repo_root}/deck-skill"
compat_dir="${skills_root}/deck"
roles=(deck-master deck-content deck-design deck-review)
current="${prefix}/share/deck/current"
installations="${prefix}/share/deck/installations"
installation="${installations}/$(date +%Y%m%d%H%M%S)-$$"
venv_dir="${installation}/share/deck/venv"
deck_bin="${prefix}/bin/deck"

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "install.sh: 缺少 $1；请安装后再运行" >&2
    exit 3
  }
}

if [ "$mode" = source ]; then
  need cargo
  need npm
else
  if [ -z "$archive_spec" ]; then
    if ! target=$(detect_target); then
      echo "install.sh: 当前平台（$(uname -s)/$(uname -m)）暂无预编译包；请使用 --from-source 从源码安装。" >&2
      exit 2
    fi
    if [ -z "$release_tag" ] && [ -f "${repo_root}/rust/Cargo.toml" ]; then
      crate_ver=$(sed -n 's/^version = "\([^"]*\)"/\1/p' "${repo_root}/rust/Cargo.toml" | head -n 1)
      if [ -n "$crate_ver" ]; then
        release_tag="v${crate_ver}"
      fi
    fi
    if [ -z "$release_tag" ]; then
      echo "install.sh: 无法确定预编译版本；请传 --version vX.Y.Z 或 --from-source。" >&2
      exit 2
    fi
    archive_spec="https://github.com/${release_repo}/releases/download/${release_tag}/deck-master-${release_tag}-${target}.tar.gz"
    if [ -z "$sha256_spec" ]; then
      sha256_spec="${archive_spec}.sha256"
    fi
  fi
  case "$archive_spec" in
    http://*|https://*)
      if [ -z "$sha256_spec" ]; then
        echo "install.sh: --archive 是远程 URL 时必须提供 --sha256（校验文件或 64 位摘要），不能跳过校验。本地文件可以省略 --sha256。请补上校验，或改用 --from-source 从源码安装。" >&2
        exit 2
      fi
      need curl
      ;;
  esac
  case "$sha256_spec" in
    http://*|https://*) need curl ;;
  esac
  need tar
fi

phase=prepare-python
install_failed() {
  local code=${1:-$?}
  if [ "$BASH_SUBSHELL" -eq 0 ]; then
    echo "install.sh: ${phase} 阶段失败（${code}）；未自动回滚或清理安装。请按相同参数重试。" >&2
  fi
  exit "$code"
}
trap install_failed ERR

if command -v uv >/dev/null 2>&1; then
  venv_python=uv
  if ! host_python=$(uv python find --offline --no-python-downloads --no-cache 3.12 2>/dev/null); then
    if [ "$dry_run" -eq 1 ]; then
      echo "install.sh: Python 3.12 尚未安装；--dry-run 不下载或写入。请先运行 uv python install 3.12，或执行不带 --dry-run 的安装。" >&2
      exit 3
    fi
    echo "install.sh: 正在用 uv 准备 Python 3.12。" >&2
    uv python install 3.12
    if ! host_python=$(uv python find --offline --no-python-downloads --no-cache 3.12 2>/dev/null); then
      echo "install.sh: prepare-python 阶段失败：uv 准备后仍找不到 Python 3.12；请检查 uv 配置后重试。" >&2
      exit 3
    fi
  fi
elif command -v python3.12 >/dev/null 2>&1; then
  venv_python=python3.12
  host_python=$(command -v python3.12)
else
  echo "install.sh: 需要 uv 或 python3.12 才能创建 deck-tools 环境" >&2
  exit 3
fi
if ! "$host_python" -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)' >/dev/null 2>&1; then
  echo "install.sh: prepare-python 阶段失败：需要可运行的 Python 3.12；请检查解释器后重试。" >&2
  exit 3
fi

if [ "$mode" = source ]; then
  [ -d "$skill_target" ] || {
    echo "install.sh: 找不到 ${skill_target}" >&2
    exit 2
  }
  for role in "${roles[@]}"; do
    [ -f "${skill_target}/${role}/SKILL.md" ] || {
      echo "install.sh: 找不到 ${skill_target}/${role}/SKILL.md" >&2
      exit 2
    }
  done
  [ -d "${skill_target}/references" ] && [ -d "${skill_target}/assets" ] || {
    echo "install.sh: 找不到共享 references 或 assets" >&2
    exit 2
  }
  [ -d "${repo_root}/rust" ] || {
    echo "install.sh: 找不到 ${repo_root}/rust" >&2
    exit 2
  }
  [ -d "${repo_root}/deck-tools" ] || {
    echo "install.sh: 找不到 ${repo_root}/deck-tools" >&2
    exit 2
  }
  [ -d "${repo_root}/frontend" ] || {
    echo "install.sh: 找不到 ${repo_root}/frontend" >&2
    exit 2
  }
fi

resolve_path() {
  local path=$1
  local guard=0
  local next dir base
  while [ -L "$path" ]; do
    next=$(readlink "$path")
    case "$next" in
      /*) path=$next ;;
      *) path="$(CDPATH= cd -- "$(dirname -- "$path")" && pwd)/$next" ;;
    esac
    guard=$((guard + 1))
    if [ "$guard" -gt 20 ]; then
      echo "install.sh: 软链接层数过多：$1" >&2
      exit 2
    fi
  done
  if [ -d "$path" ]; then
    (CDPATH= cd -- "$path" && pwd -P)
  elif [ -d "$(dirname -- "$path")" ]; then
    dir=$(CDPATH= cd -- "$(dirname -- "$path")" && pwd -P)
    base=$(basename -- "$path")
    printf '%s/%s\n' "$dir" "$base"
  else
    printf '%s\n' "$path"
  fi
}

same_link() {
  local link=$1
  local want=$2
  [ -L "$link" ] || return 1
  [ "$(resolve_path "$link")" = "$(resolve_path "$want")" ]
}

describe_entry() {
  local path=$1
  if [ -L "$path" ]; then
    printf '链接到 %s' "$(readlink "$path")"
  elif [ -d "$path" ]; then
    printf '普通目录，没有链接目标'
  elif [ -e "$path" ]; then
    printf '普通文件，没有链接目标'
  else
    printf '缺失'
  fi
}

conflicts=0
note_conflict() {
  conflicts=1
  printf '%s\n' "$1" >&2
}

action_deck=absent
if [ -e "$compat_dir" ] || [ -L "$compat_dir" ]; then
  action_deck=unmanaged
  echo "install.sh: ${compat_dir} 存在一个非本安装器管理的 deck（$(describe_entry "$compat_dir")），可能与四个职责入口抢触发；保留该路径并继续安装。" >&2
fi

actions=()
check_role() {
  local role=$1
  local dir="${skills_root}/${role}"
  if same_link "$dir" "${current}/deck-skill/${role}"; then
    actions+=(keep)
  elif [ ! -e "$dir" ] && [ ! -L "$dir" ]; then
    actions+=(create)
  else
    note_conflict "install.sh: ${dir} 已占用，不能作为 ${role} 安装。路径：${dir}；目标：$(describe_entry "$dir")。请先移走该路径（若为软链接，只删除链接，不要删除它指向的目录），然后重新运行。未改写该路径。"
    actions+=(conflict)
  fi
}

for role in "${roles[@]}"; do
  check_role "$role"
done

entry_text() {
  cat <<'ENTRY'
#!/usr/bin/env bash
set -euo pipefail
prefix=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
installation=$(CDPATH= cd -- "$prefix/share/deck/current" && pwd -P)
exec "$installation/bin/deck" "$@"
ENTRY
}

entry_action=create
if [ -e "$deck_bin" ] || [ -L "$deck_bin" ]; then
  if [ -f "$deck_bin" ] && [ ! -L "$deck_bin" ] && cmp -s "$deck_bin" <(entry_text); then
    entry_action=keep
  else
    note_conflict "install.sh: ${deck_bin} 已占用（$(describe_entry "$deck_bin")）；请手工移走此入口后重试，未改写该路径。"
  fi
fi

if [ -e "$current" ] || [ -L "$current" ]; then
  if [ ! -L "$current" ]; then
    note_conflict "install.sh: ${current} 不是受管软链接（$(describe_entry "$current")）；未改写该路径。"
  else
    resolved_current=$(resolve_path "$current")
    resolved_installations=$(resolve_path "$installations")
    case "$resolved_current" in
      "$resolved_installations"/*) ;;
      *) note_conflict "install.sh: ${current} 指向其他位置（$(describe_entry "$current")）；请手工处理，未改写该路径。" ;;
    esac
  fi
fi

check_writable_parent() {
  local path=$1 parent
  parent=$(dirname -- "$path")
  while [ ! -e "$parent" ] && [ "$parent" != / ]; do parent=$(dirname -- "$parent"); done
  if [ ! -d "$parent" ] || [ ! -w "$parent" ]; then
    note_conflict "install.sh: ${path} 的父目录不可写；请检查权限，未切换安装。"
  fi
}
check_writable_parent "$installation"
if [ "$entry_action" != keep ]; then check_writable_parent "$deck_bin"; fi
for i in "${!roles[@]}"; do
  if [ "${actions[$i]}" != keep ]; then check_writable_parent "$skills_root/${roles[$i]}"; fi
done
if [ "$conflicts" -ne 0 ]; then
  exit 2
fi

plan() {
  printf 'dry-run:'
  printf ' %s' "$@"
  printf '\n'
}

run() {
  if [ "$dry_run" -eq 1 ]; then
    plan "$@"
    return 0
  fi
  "$@"
}

if [ "$dry_run" -eq 1 ]; then
  echo "mode=${mode}"
  echo "prefix=${prefix}"
  echo "deck-bin=${deck_bin}"
  echo "venv=${venv_dir}"
  echo "skills-root=${skills_root}"
  echo "skill-entry=deck action=${action_deck}（不创建 deck）"
  for i in "${!roles[@]}"; do
    echo "skill-entry=${roles[$i]} action=${actions[$i]}"
  done
  if [ "$venv_python" = uv ]; then
    echo "venv-tool=uv"
  else
    echo "venv-tool=python3.12"
  fi
  if [ "$mode" = prebuilt ]; then
    echo "archive=${archive_spec}"
    if [ -n "$sha256_spec" ]; then
      echo "sha256=${sha256_spec}"
    fi
  fi
fi

phase=prepare
run mkdir -p "$installation"
if [ "$mode" = source ]; then
  run npm --prefix "${repo_root}/frontend" ci
  run npm --prefix "${repo_root}/frontend" run build
  run cargo install --path "${repo_root}/rust" --root "$installation" --locked
  if [ "$venv_python" = uv ]; then
    run uv venv --python 3.12 --seed "$venv_dir"
  else
    run python3.12 -m venv "$venv_dir"
  fi
  run "$venv_dir/bin/python" -m pip install "${repo_root}/deck-tools"
  run cp -R "$skill_target" "$installation/deck-skill"
else
  if [ "$dry_run" -eq 1 ]; then
    plan download-and-verify "$archive_spec" "${sha256_spec:-<no-sha256>}"
    if [ "$venv_python" = uv ]; then
      plan uv venv --python 3.12 --seed "$venv_dir"
    else
      plan python3.12 -m venv "$venv_dir"
    fi
    plan "$venv_dir/bin/python" -m pip install -r "<bundle>/requirements.lock"
    plan "$venv_dir/bin/python" -m pip install --no-deps "<bundle>/wheels/deck_tools-*.whl"
  else
    stage_dir=$(mktemp -d "${TMPDIR:-/tmp}/deck-bundle.XXXXXXXX")
    trap 'rc=$?; rm -rf -- "$stage_dir"; install_failed "$rc"' ERR
    local_archive="${stage_dir}/bundle.tar.gz"
    case "$archive_spec" in
      http://*|https://*)
        curl_code=0
        curl -fsSL "$archive_spec" -o "$local_archive" || curl_code=$?
        if [ "$curl_code" -ne 0 ]; then
          echo "install.sh: 下载预编译包失败：${archive_spec}。公开的 GitHub Release 可能还没有这个附件。请核对标签和文件名，或改用 --from-source 从源码安装。" >&2
          rm -rf -- "$stage_dir"
          exit "$curl_code"
        fi
        ;;
      *)
        [ -f "$archive_spec" ] || { echo "install.sh: 找不到预编译包 ${archive_spec}" >&2; rm -rf -- "$stage_dir"; exit 2; }
        cp "$archive_spec" "$local_archive"
        ;;
    esac
    if [ -n "$sha256_spec" ]; then
      expected_sha=""
      case "$sha256_spec" in
        http://*|https://*)
          expected_sha=$(curl -fsSL "$sha256_spec" | awk '{print $1}' | head -n 1)
          ;;
        *)
          if [ -f "$sha256_spec" ]; then
            expected_sha=$(awk '{print $1}' "$sha256_spec" | head -n 1)
          else
            expected_sha=$sha256_spec
          fi
          ;;
      esac
      "$host_python" - "$local_archive" "$expected_sha" <<'VERIFY_SHA'
import hashlib, pathlib, sys
archive = pathlib.Path(sys.argv[1])
expected = sys.argv[2].strip().lower()
if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
    raise SystemExit("install.sh: 无效的 SHA-256 校验值：" + expected)
actual = hashlib.sha256(archive.read_bytes()).hexdigest().lower()
if actual != expected:
    raise SystemExit(f"install.sh: 预编译包 SHA-256 校验失败（期望 {expected}，实际 {actual}）；已中止安装。")
VERIFY_SHA
    fi
    mkdir -p "$stage_dir/extracted"
    tar -xzf "$local_archive" -C "$stage_dir/extracted"
    [ -x "$stage_dir/extracted/bin/deck" ] || { echo "install.sh: 预编译包缺少可执行文件 bin/deck" >&2; rm -rf -- "$stage_dir"; exit 2; }
    [ -d "$stage_dir/extracted/deck-skill" ] || { echo "install.sh: 预编译包缺少 deck-skill 目录" >&2; rm -rf -- "$stage_dir"; exit 2; }
    mkdir -p "$installation/bin"
    cp "$stage_dir/extracted/bin/deck" "$installation/bin/deck"
    chmod 755 "$installation/bin/deck"
    cp -R "$stage_dir/extracted/deck-skill" "$installation/deck-skill"
    if [ "$venv_python" = uv ]; then
      uv venv --python 3.12 --seed "$venv_dir"
    else
      python3.12 -m venv "$venv_dir"
    fi
    if [ ! -f "$stage_dir/extracted/requirements.lock" ]; then
      echo "install.sh: 预编译包缺少 requirements.lock。不能在没有锁文件时用 --no-deps 安装 wheel，否则运行依赖会缺失。请换用带 requirements.lock 的包，或改用 --from-source 从源码安装。" >&2
      rm -rf -- "$stage_dir"
      exit 2
    fi
    "$venv_dir/bin/python" -m pip install -r "$stage_dir/extracted/requirements.lock"
    wheel_found=0
    for wheel in "$stage_dir/extracted"/wheels/deck_tools-*.whl; do
      if [ -f "$wheel" ]; then
        wheel_found=1
        "$venv_dir/bin/python" -m pip install --no-deps "$wheel"
      fi
    done
    if [ "$wheel_found" -eq 0 ]; then
      echo "install.sh: 预编译包缺少 wheels/deck_tools-*.whl" >&2
      rm -rf -- "$stage_dir"
      exit 2
    fi
    rm -rf -- "$stage_dir"
    trap install_failed ERR
  fi
fi

# A new shell does not keep this process's PATH, so an older deck stays first.
# The installed command text is what that next session reads.
if [ "$dry_run" -eq 0 ] && [ "$prefix" != "${HOME}/.local" ]; then
  "$host_python" - "$installation/deck-skill/references/commands.md" "$deck_bin" <<'PY'
import pathlib, sys
file = pathlib.Path(sys.argv[1])
binary = sys.argv[2]
text = file.read_text()
token = "<prefix>/bin/deck"
if token not in text:
    raise SystemExit("install.sh: 安装副本的 commands.md 缺少 <prefix>/bin/deck，无法写上这次的路径")
file.write_text(text.replace(token, binary))
PY
fi

phase=validate
if [ "$dry_run" -eq 0 ]; then
  env -u DECK_TOOLS_PYTHON -u PYTHONPATH "$installation/bin/deck" --help >/dev/null
  env -u PYTHONPATH "$venv_dir/bin/python" -c '
import importlib.metadata, json, pathlib, sys, deck_tools
root = pathlib.Path(sys.argv[1]).resolve()
assert pathlib.Path(deck_tools.__file__).resolve().is_relative_to(root)
direct = importlib.metadata.distribution("deck-tools").read_text("direct_url.json")
assert not direct or not json.loads(direct).get("dir_info", {}).get("editable", False)
for role in ("deck-master", "deck-content", "deck-design", "deck-review"):
    directory = root / "deck-skill" / role
    assert (directory / "SKILL.md").is_file() and not (directory / "SKILL.md").is_symlink()
    for name in ("references", "assets"):
        assert (directory / name).is_symlink()
        assert (directory / name).resolve() == root / "deck-skill" / name
' "$installation"
  probe_project=$(mktemp -d "${TMPDIR:-/tmp}/deck-install-check.XXXXXXXX")
  printf 'Deck installation material check' > "$probe_project/source.txt"
  env -u DECK_TOOLS_PYTHON -u PYTHONPATH "$installation/bin/deck" new "$probe_project" >/dev/null
  env -u DECK_TOOLS_PYTHON -u PYTHONPATH "$installation/bin/deck" --project "$probe_project" material add "$probe_project/source.txt" |
    "$venv_dir/bin/python" -c 'import json,sys; assert json.load(sys.stdin)["extraction"]["text"] == "Deck installation material check"'
  run rm -rf -- "$probe_project"
fi

# Normal upgrades only replace this pointer; the prepared venv never moves.
phase=switch-current
if [ "$dry_run" -eq 1 ]; then
  plan atomic-replace-current "$current" "$installation"
else
  "$host_python" - "$current" "$installation" <<'SWITCH'
import os, pathlib, secrets, sys
current = pathlib.Path(sys.argv[1])
link = current.with_name('.current-' + secrets.token_hex(16))
link.symlink_to(sys.argv[2])
try:
    os.replace(link, current)
finally:
    link.unlink(missing_ok=True)
SWITCH
fi

phase=install-entries
run mkdir -p "${prefix}/bin" "$skills_root"
if [ "$entry_action" != keep ]; then
  if [ "$dry_run" -eq 1 ]; then
    plan install-fixed-entry "$deck_bin"
  else
    "$host_python" - "$deck_bin" <(entry_text) <<'ENTRY_INSTALL'
import os, pathlib, sys, tempfile
entry = pathlib.Path(sys.argv[1])
with tempfile.NamedTemporaryFile(dir=entry.parent, prefix='.deck-entry-', delete=False) as output:
    output.write(pathlib.Path(sys.argv[2]).read_bytes())
    temporary = output.name
os.chmod(temporary, 0o755)
os.replace(temporary, entry)
ENTRY_INSTALL
  fi
fi

for i in "${!roles[@]}"; do
  if [ "${actions[$i]}" != keep ]; then
    run ln -s "$current/deck-skill/${roles[$i]}" "${skills_root}/${roles[$i]}"
  fi
done

if [ "$dry_run" -eq 1 ]; then
  plan "$deck_bin" doctor
else
  echo "已安装 deck：${deck_bin}"
  if found=$(command -v deck 2>/dev/null); then
    if [ "$(resolve_path "$found")" = "$(resolve_path "$deck_bin")" ]; then
      if [ "$prefix" != "${HOME}/.local" ]; then
        echo "当前 shell 会运行 ${deck_bin}。新开的会话使用自己的 PATH，可能先运行以前安装的 deck；请直接运行 ${deck_bin}。"
      fi
    else
      echo "PATH 上先找到的 deck：${found}"
      echo "刚安装的是 ${deck_bin}。新开的会话使用自己的 PATH，会先运行上面那个。请直接运行 ${deck_bin}，或把 ${prefix}/bin 放到 PATH 里它之前。"
    fi
  else
    echo "PATH 中没有 deck。请直接运行 ${deck_bin}，或把 ${prefix}/bin 加入 PATH。"
  fi
  echo "完整组件目录：${installation}"
  echo "四个职责入口：${skills_root}"

  phase=doctor
  # doctor writes the JSON check result to stdout before it exits.
  # Exit 3 means a tool is missing; exit 4 is a tool failure such as a timeout.
  echo "正在检查本机渲染环境（deck doctor）："
  doctor_code=0
  env -u DECK_TOOLS_PYTHON -u PYTHONPATH "$deck_bin" doctor || doctor_code=$?
  if [ "$doctor_code" -eq 3 ]; then
    echo "install.sh: 警告：deck doctor 检测到缺少部分渲染工具（退出码 3）；CLI 与基础编辑仍可用，需要渲染/回读前请按上方 JSON 提示补齐依赖。" >&2
  elif [ "$doctor_code" -ne 0 ]; then
    echo "install.sh: 警告：deck doctor 未能完成检查（退出码 ${doctor_code}）。缺工具是退出码 3；超时或工具执行失败是退出码 4。请查看上方 JSON 结果。CLI 与基础编辑仍可用。" >&2
  fi
fi
