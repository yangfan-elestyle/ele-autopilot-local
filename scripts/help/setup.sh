#!/usr/bin/env bash
# 用途：
# 1) 安装 uv（如果尚未安装）
# 2) 执行 `uv run acq-gemini.py`

set -o errexit
set -o nounset
set -o pipefail
IFS=$'\n'

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
find_repo_root() {
  local dir="$SCRIPT_DIR"
  while [[ "$dir" != "/" ]]; do
    if [[ -f "$dir/pyproject.toml" || -d "$dir/.git" ]]; then
      echo "$dir"
      return 0
    fi
    dir="$(cd "$dir/.." >/dev/null 2>&1 && pwd)"
  done
  echo "$SCRIPT_DIR"
}

REPO_ROOT="$(find_repo_root)"
cd "$REPO_ROOT"

ensure_uv() {
  if command -v uv >/dev/null 2>&1; then
    echo "[√] uv 已安装：$(uv --version)"
    return 0
  fi

  echo "[+] 正在安装 uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh

  export PATH="$HOME/.local/bin:$PATH"

  echo "[√] uv 安装完成：$(uv --version)"
}

ensure_uv
