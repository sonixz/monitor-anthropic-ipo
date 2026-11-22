#!/bin/sh
# Deploy a git ref of this public repository on the machine, or roll back.
#
#   sh deploy.sh v0.1.0               build that tag (or branch, or commit) and switch to it
#   BUILD_ONLY=1 sh deploy.sh v0.1.0  build it without switching
#   sh deploy.sh rollback             switch back to the release that ran before
#
# Run on the machine, as described in INFRASTRUCTURE.md. It needs no secret:
# the repository is public and the service reads only its own files.
# A release is switched only after it is built; if its health check fails,
# the previous release is put back.

set -eu

REF="${1:?usage: deploy.sh <tag | branch | commit | rollback>}"
REPOSITORY="https://github.com/sonixz/monitor-anthropic-ipo.git"
DATA=/data
UV="$DATA/bin/uv"
export UV_CACHE_DIR="$DATA/.cache/uv" UV_PYTHON_DOWNLOADS=never UV_COMPILE_BYTECODE=1
# One install at a time: on a 256 MB machine, parallel installs froze it (2026-11-22).
export UV_CONCURRENT_INSTALLS=1 UV_CONCURRENT_DOWNLOADS=1 UV_CONCURRENT_BUILDS=1

current() { readlink "$DATA/current" 2>/dev/null || true; }

switch_to() {
  ln -sfn "$1" "$DATA/current.new"
  mv -T "$DATA/current.new" "$DATA/current"
  install -m 755 "$1/deploy/start.sh" "$DATA/start.sh"
  if [ -f "$DATA/service.pid" ] && kill "$(cat "$DATA/service.pid")" 2>/dev/null; then
    :
  fi
  if ! pgrep -f "$DATA/start\.sh" >/dev/null 2>&1; then
    nohup /bin/sh "$DATA/start.sh" >> "$DATA/start.log" 2>&1 &
  fi
}

healthy() {
  i=0
  while [ "$i" -lt 30 ]; do
    if curl -fsS http://127.0.0.1:8000/health 2>/dev/null | grep -q "\"release\":\"$1\""; then
      return 0
    fi
    i=$((i + 1))
    sleep 1
  done
  return 1
}

PREVIOUS="$(current)"

if [ "$REF" = "rollback" ]; then
  TARGET="$(readlink "$DATA/previous" 2>/dev/null || true)"
  [ -n "$TARGET" ] && [ -f "$TARGET/.ready" ] || { echo "no previous release to roll back to"; exit 1; }
else
  if [ ! -x "$UV" ]; then
    echo "installing uv into $DATA/bin"
    curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$DATA/bin" UV_NO_MODIFY_PATH=1 sh
  fi
  [ -d "$DATA/repo/.git" ] || git clone --quiet "$REPOSITORY" "$DATA/repo"
  git -C "$DATA/repo" fetch --quiet --tags --force origin
  git -C "$DATA/repo" fetch --quiet origin '+refs/heads/*:refs/remotes/origin/*'
  SHA="$(git -C "$DATA/repo" rev-parse --short=12 --verify "origin/$REF^{commit}" 2>/dev/null \
    || git -C "$DATA/repo" rev-parse --short=12 --verify "$REF^{commit}")"
  TARGET="$DATA/releases/$SHA"
  if [ ! -f "$TARGET/.ready" ]; then
    echo "building release $SHA"
    rm -rf "$TARGET"
    mkdir -p "$TARGET"
    git -C "$DATA/repo" archive "$SHA" | tar -x -C "$TARGET"
    (cd "$TARGET" && "$UV" sync --frozen --no-dev --quiet)
    echo "$SHA" > "$TARGET/RELEASE"
    touch "$TARGET/.ready"
  fi
  if [ "${BUILD_ONLY:-}" = "1" ]; then
    echo "built release $SHA in $TARGET; not switched"
    exit 0
  fi
fi

RELEASE="$(cat "$TARGET/RELEASE")"
echo "switching to release $RELEASE"
switch_to "$TARGET"

if healthy "$RELEASE"; then
  if [ -n "$PREVIOUS" ] && [ "$PREVIOUS" != "$TARGET" ]; then
    ln -sfn "$PREVIOUS" "$DATA/previous"
  fi
  echo "deployed: $(date -u +%FT%TZ) release $RELEASE (previous: ${PREVIOUS:-none})" | tee -a "$DATA/deploy.log"
  # Keep the five most recent releases.
  ls -1dt "$DATA"/releases/*/ 2>/dev/null | tail -n +6 | while read -r old; do
    old="${old%/}"
    [ "$old" = "$TARGET" ] || [ "$old" = "$PREVIOUS" ] || rm -rf "$old"
  done
else
  echo "release $RELEASE did not become healthy" | tee -a "$DATA/deploy.log"
  if [ -n "$PREVIOUS" ] && [ "$PREVIOUS" != "$TARGET" ]; then
    echo "putting back $(cat "$PREVIOUS/RELEASE")" | tee -a "$DATA/deploy.log"
    switch_to "$PREVIOUS"
  fi
  exit 1
fi
