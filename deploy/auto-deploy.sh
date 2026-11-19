#!/usr/bin/env bash
# Pulls new commits from GitHub and rebuilds only what changed.
# Run by planer-autodeploy.timer every minute; safe to run by hand too.
#
#   PLANER_DIR     project checkout (default: the repo this script lives in)
#   DEPLOY_BRANCH  branch to follow (default: claude/great-gates-uwg8kl)
set -euo pipefail

PLANER_DIR="${PLANER_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-claude/great-gates-uwg8kl}"
DOCKER="${DOCKER:-docker}"

cd "$PLANER_DIR"

# One deploy at a time: a slow build must not overlap the next tick.
exec 9>"${TMPDIR:-/tmp}/planer-autodeploy.lock"
flock -n 9 || { echo "Another deploy is still running"; exit 0; }

git fetch --quiet origin "$DEPLOY_BRANCH"
head="$(git rev-parse HEAD)"
target="$(git rev-parse FETCH_HEAD)"

# The last commit that actually reached the containers. A failed build leaves it behind,
# so the next tick retries instead of thinking everything is up to date.
state_file="$(git rev-parse --git-dir)/planer-deployed"
# First run: whatever is checked out now is what the running containers were built from.
[ -s "$state_file" ] || echo "$head" >"$state_file"
deployed="$(cat "$state_file")"

if [ "$head" != "$target" ]; then
  # Never overwrite hand edits on the server; untracked files (.env, keys) are fine.
  if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "Local changes in tracked files, skipping deploy of ${target:0:7}:" >&2
    git status --short --untracked-files=no >&2
    exit 1
  fi
  # Only move forward along the branch; a rewritten history needs a human.
  if ! git merge --ff-only --quiet "$target"; then
    echo "Cannot fast-forward ${head:0:7} to ${target:0:7}; deploy by hand" >&2
    exit 1
  fi
  echo "Updated ${head:0:7} -> ${target:0:7}: $(git log -1 --format=%s)"
  head="$target"
fi

[ "$deployed" = "$head" ] && exit 0

changed="$(git diff --name-only "$deployed" "$head")"
services=()
if grep -qE '^(docker-compose\.yml|\.env\.example)$' <<<"$changed"; then
  services=(backend webapp)
else
  grep -q '^backend/' <<<"$changed" && services+=(backend)
  grep -q '^webapp/' <<<"$changed" && services+=(webapp)
fi

if [ "${#services[@]}" -gt 0 ]; then
  echo "Rebuilding: ${services[*]}"
  "$DOCKER" compose up -d --build "${services[@]}"
else
  echo "No backend or webapp changes, nothing to rebuild"
fi
echo "$head" >"$state_file"
echo "Deployed ${head:0:7}"
