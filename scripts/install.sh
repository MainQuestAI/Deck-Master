#!/usr/bin/env bash
# Install the Rust CLI, a dedicated deck-tools venv, and Codex skill links.
# Does not activate or roll back a managed release.
set -euo pipefail

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
skill_target="${repo_root}/deck-skill"
compat_dir="${skills_root}/deck"
roles=(deck-master deck-content deck-design deck-review)
venv_dir="${prefix}/share/deck/venv"
deck_bin="${prefix}/bin/deck"

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "install.sh: 缺少 $1；请安装后再运行" >&2
    exit 3
  }
}

need cargo
need npm
if command -v uv >/dev/null 2>&1; then
  venv_python=uv
elif command -v python3.12 >/dev/null 2>&1; then
  venv_python=python3.12
else
  echo "install.sh: 需要 uv 或 python3.12 才能创建 deck-tools 环境" >&2
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

conflicts=0
note_conflict() {
  conflicts=1
  printf '%s\n' "$1" >&2
}

action_deck=absent
if same_link "$compat_dir" "$skill_target"; then
  action_deck=remove
elif [ -e "$compat_dir" ] || [ -L "$compat_dir" ]; then
  action_deck=unmanaged
  echo "install.sh: ${compat_dir} 还有一个非本安装器管理的 deck（$(describe_entry "$compat_dir")），可能与四个职责入口抢触发；保留该路径并继续安装。" >&2
fi

managed_wrapper() {
  local dir=$1
  local role=$2
  local entry
  [ -d "$dir" ] && [ ! -L "$dir" ] || return 1
  { same_link "${dir}/SKILL.md" "${skill_target}/${role}.md" \
    || same_link "${dir}/SKILL.md" "${skill_target}/${role}/SKILL.md"; } \
    && same_link "${dir}/references" "${skill_target}/references" \
    && same_link "${dir}/assets" "${skill_target}/assets" || return 1
  # Include hidden entries so upgrading never discards an author's extra files.
  for entry in "$dir"/* "$dir"/.[!.]* "$dir"/..?*; do
    [ -e "$entry" ] || [ -L "$entry" ] || continue
    case "${entry##*/}" in
      SKILL.md|references|assets) ;;
      *) return 1 ;;
    esac
  done
}

actions=()
check_role() {
  local role=$1
  local dir="${skills_root}/${role}"
  if same_link "$dir" "${skill_target}/${role}"; then
    actions+=(keep)
  elif [ ! -e "$dir" ] && [ ! -L "$dir" ]; then
    actions+=(create)
  elif managed_wrapper "$dir" "$role"; then
    actions+=(upgrade)
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

run npm --prefix "${repo_root}/frontend" ci
run npm --prefix "${repo_root}/frontend" run build
run cargo install --path "${repo_root}/rust" --root "${prefix}" --force --locked

# A second run must not fail after cargo install has already replaced bin/deck.
# Do not pass --clear: that would wipe a venv the previous run already filled.
if [ -x "${venv_dir}/bin/python" ]; then
  if [ "$dry_run" -eq 1 ]; then
    echo "dry-run: reuse venv ${venv_dir}"
  fi
elif [ "$venv_python" = uv ]; then
  run uv venv --python 3.12 --seed "${venv_dir}"
else
  run python3.12 -m venv "${venv_dir}"
fi
run "${venv_dir}/bin/python" -m pip install -e "${repo_root}/deck-tools"

link_role() {
  local role=$1
  local action=$2
  local dir="${skills_root}/${role}"
  if [ "$action" = keep ]; then
    if [ "$dry_run" -eq 1 ]; then
      echo "dry-run: keep ${dir} -> ${skill_target}/${role}"
    fi
    return 0
  fi
  if [ "$action" = upgrade ]; then
    run rm -- "${dir}/SKILL.md" "${dir}/references" "${dir}/assets"
    run rmdir -- "$dir"
  fi
  run ln -s "${skill_target}/${role}" "$dir"
}

if [ "$action_deck" = remove ]; then
  run rm -- "$compat_dir"
fi
run mkdir -p "$skills_root"
for i in "${!roles[@]}"; do
  link_role "${roles[$i]}" "${actions[$i]}"
done

if [ "$dry_run" -eq 0 ]; then
  echo "已安装 deck：${deck_bin}"
  if command -v deck >/dev/null 2>&1; then
    echo "PATH 解析到的 deck：$(command -v deck)"
  else
    echo "PATH 中没有 deck。请把 ${prefix}/bin 加入 PATH，或直接运行 ${deck_bin}。"
  fi
  echo "deck-tools 环境：${venv_dir}"
  for role in "${roles[@]}"; do
    echo "Skill 链接：${skills_root}/${role} -> ${skill_target}/${role}"
  done
fi
