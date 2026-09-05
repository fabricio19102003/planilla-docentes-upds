#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/common.sh"

require_command curl

if [[ "${SKIP_BUILD:-0}" != "1" ]]; then
  "$SCRIPT_DIR/build.sh"
else
  "$SCRIPT_DIR/preflight.sh"
fi

release_tag="$(env_value IMAGE_TAG)"
umask 077
mkdir -p "$STATE_DIR"

info "Starting PostgreSQL only"
compose up --detach db
wait_for_healthy db 60

info "Stopping application traffic before backup and migration"
compose stop app backend >/dev/null 2>&1 || true

if [[ -z "${PREMIGRATION_BACKUP_PATH:-}" ]]; then
  backup_path="$("$SCRIPT_DIR/backup.sh" | tail -n 1)"
  cat >&2 <<EOF
Deployment paused fail-closed before migration.
Copy both files below to approved encrypted external storage:
  $backup_path
  $backup_path.sha256

After verifying the external copy, resume with:
  SKIP_BUILD=1 PREMIGRATION_BACKUP_PATH='$backup_path' CONFIRM_EXTERNAL_BACKUP=YES deploy/scripts/deploy.sh
EOF
  exit 3
fi

"$SCRIPT_DIR/migrate.sh"

info "Starting the reviewed release"
compose up --detach --no-build backend app
wait_for_healthy backend 60
wait_for_healthy app 30

host_port="$(env_value APP_HOST_PORT)"
curl --fail --silent --show-error --max-time 10 "http://127.0.0.1:$host_port/ready" >/dev/null

if [[ -f "$STATE_DIR/current-release" ]]; then
  cp "$STATE_DIR/current-release" "$STATE_DIR/previous-release"
fi
printf '%s\n' "$release_tag" >"$STATE_DIR/current-release"
chmod 600 "$STATE_DIR/current-release"
[[ ! -f "$STATE_DIR/previous-release" ]] || chmod 600 "$STATE_DIR/previous-release"

info "Release $release_tag is healthy on the loopback endpoint"
