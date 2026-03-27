#!/usr/bin/env bash
# legacy

set -euo pipefail

ROOT_DIR="${ROOT_DIR:-/home/container}"
REPO_URL="${REPO_URL:-https://github.com/leizov/Seal-Playerok-Bot.git}"
REPO_BRANCH="${REPO_BRANCH:-main}"
PYTHON_BIN=""

log() {
  printf '[container-install] %s\n' "$*"
}

warn() {
  printf '[container-install][warn] %s\n' "$*" >&2
}

fail() {
  printf '[container-install][error] %s\n' "$*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

detect_python() {
  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
    return 0
  fi
  fail "Required command not found: python/python3"
}

find_nested_project_dir() {
  local dir
  for dir in "$ROOT_DIR"/*; do
    [ -d "$dir" ] || continue
    if [ -f "$dir/bot.py" ] && [ -f "$dir/requirements.txt" ]; then
      printf '%s\n' "$dir"
      return 0
    fi
  done
  return 1
}

clone_project() {
  local tmp_dir
  tmp_dir="$(mktemp -d)"
  log "Cloning ${REPO_URL} (${REPO_BRANCH})..."
  git clone --depth 1 --branch "$REPO_BRANCH" "$REPO_URL" "$tmp_dir/repo"
  cp -a "$tmp_dir/repo/." "$ROOT_DIR/"
  rm -rf "$tmp_dir"
}

flatten_nested_project() {
  local src_dir="$1"
  log "Project found in nested directory: ${src_dir}"
  log "Moving project files to ${ROOT_DIR}..."
  cp -a "$src_dir/." "$ROOT_DIR/"
}

ensure_app_entrypoint() {
  local app_file="$ROOT_DIR/app.py"
  log "Writing ${app_file} entrypoint..."
  cat > "$app_file" <<'PY'
import os
import runpy

ROOT = os.path.dirname(os.path.abspath(__file__))
BOT_FILE = os.path.join(ROOT, "bot.py")

if not os.path.isfile(BOT_FILE):
    raise FileNotFoundError(f"bot.py not found at {BOT_FILE}")

runpy.run_path(BOT_FILE, run_name="__main__")
PY
}

check_python_version() {
  local current
  current="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")')"
  if "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)
PY
  then
    log "Python version is compatible: ${current}"
  else
    warn "Current Python is ${current}. This project requires Python 3.12.x."
    warn "Select a Python 3.12 container image in panel settings before start."
  fi
}

main() {
  [ -d "$ROOT_DIR" ] || fail "Root directory does not exist: $ROOT_DIR"

  require_cmd git
  detect_python

  cd "$ROOT_DIR"

  if [ -f "$ROOT_DIR/bot.py" ] && [ -f "$ROOT_DIR/requirements.txt" ]; then
    log "Project files already exist in ${ROOT_DIR}"
  else
    if nested_dir="$(find_nested_project_dir)"; then
      flatten_nested_project "$nested_dir"
    else
      clone_project
    fi
  fi

  [ -f "$ROOT_DIR/bot.py" ] || fail "bot.py is missing in ${ROOT_DIR}"
  [ -f "$ROOT_DIR/requirements.txt" ] || fail "requirements.txt is missing in ${ROOT_DIR}"

  ensure_app_entrypoint
  check_python_version

  log "Done."
  log "Use these startup variables in panel:"
  log "  PY_FILE=app.py"
  log "  REQUIREMENTS_FILE=requirements.txt"
  log "  PY_PACKAGES="
  log "  AUTO_UPDATE=1"
}

main "$@"
