#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd -- "$DEPLOY_DIR/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$DEPLOY_DIR/compose.production.yml}"
ENV_FILE="${ENV_FILE:-$DEPLOY_DIR/.env.production}"
STATE_DIR="${STATE_DIR:-$DEPLOY_DIR/state}"

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

info() {
  printf '==> %s\n' "$*"
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

require_file() {
  [[ -f "$1" ]] || die "Required file not found: $1"
}

env_value() {
  local key="$1"
  awk -v key="$key" '
    $0 !~ /^[[:space:]]*#/ && index($0, key "=") == 1 {
      sub(/^[^=]*=/, "")
      sub(/\r$/, "")
      print
      exit
    }
  ' "$ENV_FILE"
}

compose() {
  docker compose --env-file "$ENV_FILE" --file "$COMPOSE_FILE" "$@"
}

ensure_private_env() {
  local mode
  mode="$(stat -c '%a' "$ENV_FILE")"
  (( 10#$mode % 100 == 0 )) || die "$ENV_FILE must not be readable or writable by group/others (use chmod 600)"
}

wait_for_healthy() {
  local service="$1"
  local attempts="${2:-60}"
  local container_id status

  for ((i = 1; i <= attempts; i++)); do
    container_id="$(compose ps -q "$service")"
    if [[ -n "$container_id" ]]; then
      status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id")"
      [[ "$status" == "healthy" ]] && return 0
      [[ "$status" == "exited" || "$status" == "dead" || "$status" == "unhealthy" ]] && break
    fi
    sleep 2
  done

  compose ps "$service" >&2 || true
  compose logs --tail=80 "$service" >&2 || true
  die "Service did not become healthy: $service"
}
