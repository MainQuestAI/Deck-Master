#!/usr/bin/env bash
# Install the Rust CLI, a dedicated deck-tools venv, and the Codex skill link.
# Does not activate or roll back a managed release.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: install.sh [--prefix DIR] [--skill-dir PATH] [--dry-run]

Install deck, a dedicated deck-tools venv, and link deck-skill for Codex.

  --prefix DIR     cargo install root (default: ~/.local)
  --skill-dir PATH Codex skill path (default: ~/.codex/skills/deck)
  --dry-run        print the plan and check the skill path; do not write
EOF
}

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
prefix="${HOME}/.local"
skill_dir="${HOME}/.codex/skills/deck"
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

skill_target="${repo_root}/deck-skill"
venv_dir="${prefix}/share/deck/venv"
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

skill_link_state() {
  if [ -L "$skill_dir" ]; then
    current=$(readlink "$skill_dir")
    case "$current" in
      /*) ;;
      *) current="$(CDPATH= cd -- "$(dirname -- "$skill_dir")" && pwd -P)/$current" ;;
    esac
    if [ -d "$current" ]; then
      current=$(CDPATH= cd -- "$current" && pwd -P)
    fi
    target=$(CDPATH= cd -- "$skill_target" && pwd -P)
    if [ "$current" = "$target" ]; then
      return 1
    fi
    return 3
  fi
  if [ -e "$skill_dir" ]; then
    return 2
  fi
  return 0
}

link_status=0
skill_link_state || link_status=$?
if [ "$link_status" -eq 2 ]; then
  echo "install.sh: ${skill_dir} 已存在且不是指向 deck-skill 的软链接；请改用 --skill-dir 或先移走该路径" >&2
  exit 2
fi
if [ "$link_status" -eq 3 ]; then
  echo "install.sh: ${skill_dir} 已存在且指向其他位置；请改用 --skill-dir 或先移走该链接" >&2
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
  echo "venv=${venv_dir}"
  echo "skill-dir=${skill_dir}"
  echo "skill-target=${skill_target}"
  if [ "$link_status" -eq 1 ]; then
    echo "skill-link=already"
  else
    echo "skill-link=create"
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

if [ "$link_status" -eq 1 ]; then
  if [ "$dry_run" -eq 1 ]; then
    echo "dry-run: keep existing skill link ${skill_dir}"
  fi
else
  run mkdir -p "$(dirname -- "${skill_dir}")"
  run ln -s "${skill_target}" "${skill_dir}"
fi

if [ "$dry_run" -eq 0 ]; then
  echo "已安装 deck：${prefix}/bin/deck"
  echo "deck-tools 环境：${venv_dir}"
  echo "Skill 链接：${skill_dir} -> ${skill_target}"
  echo "如 ${prefix}/bin 不在 PATH 中，请加入后再运行 deck。"
fi
