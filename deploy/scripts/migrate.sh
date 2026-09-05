#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/common.sh"

require_file "$ENV_FILE"
ensure_private_env

backup_path="${PREMIGRATION_BACKUP_PATH:-}"
[[ -n "$backup_path" ]] || die "Set PREMIGRATION_BACKUP_PATH to the fresh backup produced by backup.sh"
backup_path="$(realpath "$backup_path")"
backup_root="$(realpath "$STATE_DIR/backups")"
[[ "$backup_path" == "$backup_root"/* ]] || die "PREMIGRATION_BACKUP_PATH must be inside $backup_root"
require_file "$backup_path"
require_file "$backup_path.sha256"

if [[ "${CONFIRM_EXTERNAL_BACKUP:-}" != "YES" ]]; then
  die "Migration requires CONFIRM_EXTERNAL_BACKUP=YES after this exact backup and checksum are copied to approved external storage"
fi

(cd "$(dirname "$backup_path")" && sha256sum --check "$(basename "$backup_path").sha256")
backup_age_seconds=$(( $(date +%s) - $(stat -c '%Y' "$backup_path") ))
(( backup_age_seconds <= 86400 )) || die "Pre-migration backup is older than 24 hours; create and externally copy a fresh backup"

info "Applying Alembic migrations as a separate fail-closed gate"
compose run --rm --no-deps backend alembic upgrade head

info "Verifying the database is on the packaged Alembic head"
current_output="$(compose run --rm --no-deps backend alembic current)"
grep -q '(head)' <<<"$current_output" || die "Alembic current is not a packaged head"
info "Migration gate passed"
