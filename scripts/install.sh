#!/usr/bin/env bash
# Install the Rust CLI, a dedicated deck-tools venv, and Codex skill links.
# Does not activate or roll back a managed release.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: install.sh [--prefix DIR] [--skill-dir PATH | --skills-root DIR] [--dry-run]

Install deck, a dedicated deck-tools venv, and Codex skill links.

  --prefix DIR       cargo install root (default: ~/.local)
  --skill-dir PATH   install only the compatibility deck entry at PATH
                     (default when neither skill flag is set: ~/.codex/skills/deck)
  --skills-root DIR  install deck-master, deck-content, deck-design,
                     deck-review, and the compatibility deck entry under DIR
  --dry-run          print the plan and check skill paths; do not write

--skill-dir and --skills-root cannot be used together. With neither flag,
only the CLI, the tool environment, and the compatibility deck entry are
installed or updated.
EOF
}

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
prefix="${HOME}/.local"
skill_dir="${HOME}/.codex/skills/deck"
skills_root=""
skill_dir_set=0
skills_root_set=0
dry_run=0

while [ $# -gt 0 ]; do
  case "$1" in
    --prefix)
      [ $# -ge 2 ] || { echo "install.sh: --prefix 需要目录" >&2; exit 2; }
      prefix=$2
      shift 2
      ;;
    --skill-dir)
      [ $# -ge 2 ] || { echo "install.sh: --skill-dir 需要路径" >&2; exit 2; }
      skill_dir=$2
      skill_dir_set=1
      shift 2
      ;;
    --skills-root)
      [ $# -ge 2 ] || { echo "install.sh: --skills-root 需要目录" >&2; exit 2; }
      skills_root=$2
      skills_root_set=1
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

if [ "$skill_dir_set" -eq 1 ] && [ "$skills_root_set" -eq 1 ]; then
  echo "install.sh: --skill-dir 与 --skills-root 不能同时使用" >&2
  exit 2
fi

skill_target="${repo_root}/deck-skill"
venv_dir="${prefix}/share/deck/venv"
deck_bin="${prefix}/bin/deck"
mode=compat
compat_dir=$skill_dir
if [ "$skills_root_set" -eq 1 ]; then
  [ -n "$skills_root" ] || { echo "install.sh: --skills-root 需要目录" >&2; exit 2; }
  mode=roles
  skills_root=${skills_root%/}
  compat_dir="${skills_root}/deck"
fi

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
[ -f "${skill_target}/SKILL.md" ] || {
  echo "install.sh: 找不到 ${skill_target}/SKILL.md" >&2
  exit 2
}
if [ "$mode" = roles ]; then
  for role in deck-master deck-content deck-design deck-review; do
    [ -f "${skill_target}/${role}.md" ] || {
      echo "install.sh: 找不到 ${skill_target}/${role}.md" >&2
      exit 2
    }
  done
  [ -d "${skill_target}/references" ] && [ -d "${skill_target}/assets" ] || {
    echo "install.sh: 找不到共享 references 或 assets" >&2
    exit 2
  }
fi
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
  elif [ -f "$path" ]; then
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

action_deck=create
action_deck_master=create
action_deck_content=create
action_deck_design=create
action_deck_review=create

if [ -L "$compat_dir" ]; then
  if same_link "$compat_dir" "$skill_target"; then
    action_deck=keep
  else
    if [ "$mode" = compat ]; then
      note_conflict "install.sh: ${compat_dir} 已存在且指向其他位置：$(readlink "$compat_dir")；请改用 --skill-dir，或只删除该软链接（不要删除它指向的目录）后重新运行"
    else
      note_conflict "install.sh: ${compat_dir} 已存在且指向其他位置：$(readlink "$compat_dir")。未改写该路径。"
    fi
  fi
elif [ -e "$compat_dir" ]; then
  if [ "$mode" = compat ]; then
    note_conflict "install.sh: ${compat_dir} 已存在且不是指向 deck-skill 的软链接（$(describe_entry "$compat_dir")）；请改用 --skill-dir 或先移走该路径"
  else
    note_conflict "install.sh: ${compat_dir} 已存在且不是指向 deck-skill 的软链接（$(describe_entry "$compat_dir")）。未改写该路径。"
  fi
fi

check_role() {
  local role=$1
  local dir=$2
  local skill_file=$3
  local result=create
  if [ ! -e "$dir" ] && [ ! -L "$dir" ]; then
    result=create
  elif [ -L "$dir" ] || [ ! -d "$dir" ]; then
    note_conflict "install.sh: ${dir} 已占用，不能作为 ${role} 安装。路径：${dir}；目标：$(describe_entry "$dir")。未改写该路径。"
    result=conflict
  elif same_link "${dir}/SKILL.md" "$skill_file" \
    && same_link "${dir}/references" "${skill_target}/references" \
    && same_link "${dir}/assets" "${skill_target}/assets"; then
    result=keep
  else
    note_conflict "install.sh: ${dir} 已占用，不能作为 ${role} 安装。未改写该路径。
路径：${dir}
SKILL.md：$(describe_entry "${dir}/SKILL.md")
references：$(describe_entry "${dir}/references")
assets：$(describe_entry "${dir}/assets")"
    result=conflict
  fi
  case "$role" in
    deck-master) action_deck_master=$result ;;
    deck-content) action_deck_content=$result ;;
    deck-design) action_deck_design=$result ;;
    deck-review) action_deck_review=$result ;;
  esac
}

if [ "$mode" = roles ]; then
  check_role deck-master "${skills_root}/deck-master" "${skill_target}/deck-master.md"
  check_role deck-content "${skills_root}/deck-content" "${skill_target}/deck-content.md"
  check_role deck-design "${skills_root}/deck-design" "${skill_target}/deck-design.md"
  check_role deck-review "${skills_root}/deck-review" "${skill_target}/deck-review.md"
fi

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
  echo "skill-mode=${mode}"
  echo "skill-dir=${compat_dir}"
  echo "skill-target=${skill_target}"
  if [ "$mode" = roles ]; then
    echo "skills-root=${skills_root}"
  fi
  if [ "$action_deck" = keep ]; then
    echo "skill-link=already"
  else
    echo "skill-link=create"
  fi
  if [ "$mode" = roles ]; then
    echo "skill-entry=deck-master action=${action_deck_master}"
    echo "skill-entry=deck-content action=${action_deck_content}"
    echo "skill-entry=deck-design action=${action_deck_design}"
    echo "skill-entry=deck-review action=${action_deck_review}"
  fi
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

link_compat() {
  if [ "$action_deck" = keep ]; then
    if [ "$dry_run" -eq 1 ]; then
      echo "dry-run: keep existing skill link ${compat_dir}"
    fi
    return 0
  fi
  run mkdir -p "$(dirname -- "${compat_dir}")"
  run ln -s "${skill_target}" "${compat_dir}"
}

link_role() {
  local role=$1
  local action=$2
  local dir="${skills_root}/${role}"
  if [ "$action" = keep ]; then
    if [ "$dry_run" -eq 1 ]; then
      echo "dry-run: keep existing skill link ${dir}"
    fi
    return 0
  fi
  run mkdir -p "${dir}"
  run ln -s "${skill_target}/${role}.md" "${dir}/SKILL.md"
  run ln -s "${skill_target}/references" "${dir}/references"
  run ln -s "${skill_target}/assets" "${dir}/assets"
}

link_compat
if [ "$mode" = roles ]; then
  link_role deck-master "$action_deck_master"
  link_role deck-content "$action_deck_content"
  link_role deck-design "$action_deck_design"
  link_role deck-review "$action_deck_review"
fi

if [ "$dry_run" -eq 0 ]; then
  echo "已安装 deck：${deck_bin}"
  if command -v deck >/dev/null 2>&1; then
    echo "PATH 解析到的 deck：$(command -v deck)"
  else
    echo "PATH 中没有 deck。请把 ${prefix}/bin 加入 PATH，或直接运行 ${deck_bin}。"
  fi
  echo "deck-tools 环境：${venv_dir}"
  echo "Skill 链接：${compat_dir} -> ${skill_target}"
  if [ "$mode" = roles ]; then
    for role in deck-master deck-content deck-design deck-review; do
      echo "Skill 链接：${skills_root}/${role}/SKILL.md -> ${skill_target}/${role}.md"
    done
  fi
fi
