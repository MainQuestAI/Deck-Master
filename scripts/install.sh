#!/usr/bin/env bash
# Install the Rust CLI, a dedicated deck-tools venv, and Codex skill links.
# Prepare a complete local component group before switching one current link.
set -Eeuo pipefail

usage() {
  cat <<'EOF'
用法：install.sh [--prefix DIR] [--skills-root DIR] [--dry-run]

安装 deck、独立的 deck-tools 环境和四个 Codex 职责入口。

  --prefix DIR       CLI 安装根目录（默认 ~/.local）
  --skills-root DIR  技能根目录（默认 ~/.codex/skills）
  --dry-run          打印计划并检查技能路径，不写入

默认将 deck-master、deck-content、deck-design、deck-review 整个目录
软链接到 ~/.codex/skills；--skills-root 更换目录。不再安装兼容入口 deck。
EOF
}

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
prefix="${HOME}/.local"
skills_root="${HOME}/.codex/skills"
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

need cargo
need npm
phase=prepare-python
install_failed() {
  local code=$?
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

# Cargo metadata plus the associated built artifact identify an old managed
# binary. A stale Cargo record alone must not authorize replacing another tool.
legacy_source=""
if [ -f "$deck_bin" ] && [ ! -L "$deck_bin" ]; then
  legacy_source=$("$host_python" - "$prefix" <<'LEGACY_SOURCE' || true
import json, pathlib, sys, urllib.parse
prefix = pathlib.Path(sys.argv[1])
try:
    installs = json.loads((prefix / '.crates2.json').read_text())['installs']
    for key, value in installs.items():
        if not key.startswith('deck ') or value.get('bins') != ['deck']:
            continue
        crate = pathlib.Path(urllib.parse.unquote(key.split('(path+file://', 1)[1].rstrip(')')))
        repo = crate.parent
        built = crate / 'target/release/deck'
        if ((crate / 'Cargo.toml').is_file() and (repo / 'deck-tools/pyproject.toml').is_file()
                and (repo / 'deck-skill/deck-master/SKILL.md').is_file() and built.is_file()
                and built.read_bytes() == (prefix / 'bin/deck').read_bytes()):
            print(repo.resolve())
            raise SystemExit(0)
except (OSError, ValueError, KeyError, IndexError):
    pass
raise SystemExit(1)
LEGACY_SOURCE
  )
fi

conflicts=0
note_conflict() {
  conflicts=1
  printf '%s\n' "$1" >&2
}

entry_receipt() {
  "$host_python" "$script_dir/install_entry.py" "$1" "$prefix" "$2" "$3" \
    "$skill_target" "$legacy_source" "${4:-}"
}

require_recorded_entry() {
  entry_receipt check "$1" "$2" >/dev/null || {
    local code=$?
    echo "install.sh: 入口在记录后发生变化或迁移凭据不可读取：$1；请保留该入口和用户文件，核对后重试。" >&2
    return "$code"
  }
}

action_deck=absent
if same_link "$compat_dir" "$skill_target" || { [ -n "$legacy_source" ] && same_link "$compat_dir" "$legacy_source/deck-skill"; } \
  || [ "$(entry_receipt check "$compat_dir" deck)" = replace ]; then
  action_deck=remove
elif [ -e "$compat_dir" ] || [ -L "$compat_dir" ]; then
  action_deck=unmanaged
  echo "install.sh: ${compat_dir} 还有一个非本安装器管理的 deck（$(describe_entry "$compat_dir")），可能与四个职责入口抢触发；保留该路径并继续安装。" >&2
fi

wrapper_for_source() {
  local dir=$1
  local role=$2
  local source_root=$3
  local entry
  [ -d "$dir" ] && [ ! -L "$dir" ] || return 1
  { same_link "${dir}/SKILL.md" "${source_root}/${role}.md" \
    || same_link "${dir}/SKILL.md" "${source_root}/${role}/SKILL.md"; } \
    && same_link "${dir}/references" "${source_root}/references" \
    && same_link "${dir}/assets" "${source_root}/assets" || return 1
  # Include hidden entries so upgrading never discards an author's extra files.
  for entry in "$dir"/* "$dir"/.[!.]* "$dir"/..?*; do
    [ -e "$entry" ] || [ -L "$entry" ] || continue
    case "${entry##*/}" in
      SKILL.md|references|assets) ;;
      *) return 1 ;;
    esac
  done
}

managed_wrapper() {
  wrapper_for_source "$1" "$2" "$skill_target" || {
    [ -n "$legacy_source" ] && wrapper_for_source "$1" "$2" "$legacy_source/deck-skill"
  }
}

actions=()
check_role() {
  local role=$1
  local dir="${skills_root}/${role}" saved_action
  if same_link "$dir" "${current}/deck-skill/${role}"; then
    actions+=(keep)
  elif same_link "$dir" "${skill_target}/${role}" || { [ -n "$legacy_source" ] && same_link "$dir" "$legacy_source/deck-skill/$role"; }; then
    actions+=(replace)
  elif [ ! -e "$dir" ] && [ ! -L "$dir" ]; then
    actions+=(create)
  elif managed_wrapper "$dir" "$role"; then
    actions+=(upgrade)
  elif saved_action=$(entry_receipt check "$dir" "$role"); then
    actions+=("$saved_action")
  else
    note_conflict "install.sh: ${dir} 已占用，不能作为 ${role} 安装。路径：${dir}；目标：$(describe_entry "$dir")。
SKILL.md：$(describe_entry "${dir}/SKILL.md")
references：$(describe_entry "${dir}/references")
assets：$(describe_entry "${dir}/assets")
请先移走该路径；若为软链接，只删除链接，不要删除它指向的目录，然后重新运行。未改写该路径。"
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
  elif [ -n "$legacy_source" ]; then
    entry_action=migrate
  else
    note_conflict "install.sh: ${deck_bin} 已占用且无法确认归属；请手工移走此入口后重试，未改写该路径。"
  fi
fi
if [ -e "$current" ] || [ -L "$current" ]; then
  if [ ! -L "$current" ]; then
    note_conflict "install.sh: ${current} 不是受管软链接；未改写该路径。"
  else
    resolved_current=$(resolve_path "$current")
    resolved_installations=$(resolve_path "$installations")
    case "$resolved_current" in
      "$resolved_installations"/*) ;;
      *) note_conflict "install.sh: ${current} 指向其他位置；请手工处理，未改写该路径。" ;;
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
fi

phase=prepare
run mkdir -p "$installation"
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
import os, pathlib, sys
current = pathlib.Path(sys.argv[1])
import secrets
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
# Preserve ownership before replacing the binary or removing any old link.
# The record binds each entry's inode and link targets, not stale Cargo data.
if [ "$dry_run" -eq 0 ]; then
  if [ "$action_deck" = remove ]; then entry_receipt record "$compat_dir" deck replace; fi
  for i in "${!roles[@]}"; do
    case "${actions[$i]}" in
      replace|upgrade) entry_receipt record "$skills_root/${roles[$i]}" "${roles[$i]}" "${actions[$i]}" ;;
    esac
  done
fi
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
link_role() {
  local role=$1 action=$2 dir="${skills_root}/$1"
  if [ "$action" = keep ]; then return; fi
  if [ "$dry_run" -eq 0 ] && { [ "$action" = upgrade ] || [ "$action" = replace ]; }; then
    require_recorded_entry "$dir" "$role"
  fi
  if [ "$action" = upgrade ]; then
    run rm -f -- "$dir/SKILL.md" "$dir/references" "$dir/assets"
    run rmdir -- "$dir"
  elif [ "$action" = replace ]; then
    run rm -- "$dir"
  fi
  run ln -s "$current/deck-skill/$role" "$dir"
}
if [ "$action_deck" = remove ]; then
  if [ "$dry_run" -eq 0 ]; then require_recorded_entry "$compat_dir" deck; fi
  run rm -- "$compat_dir"
fi
for i in "${!roles[@]}"; do link_role "${roles[$i]}" "${actions[$i]}"; done
if [ "$dry_run" -eq 0 ]; then
  entry_receipt clear "$compat_dir" deck
  for role in "${roles[@]}"; do entry_receipt clear "$skills_root/$role" "$role"; done
  echo "已安装 deck：${deck_bin}"
  echo "完整组件目录：${installation}"
  echo "四个职责入口：${skills_root}"
  if [ "$entry_action" = migrate ]; then
    echo "旧布局 venv 和源码保留供旧进程使用；停止旧进程后可另行处理。"
  fi
fi
