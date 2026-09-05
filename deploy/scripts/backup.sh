#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/common.sh"

require_command docker
require_command sha256sum
require_file "$ENV_FILE"
ensure_private_env

wait_for_healthy db 30

umask 077
backup_dir="$STATE_DIR/backups"
mkdir -p "$backup_dir"
timestamp="$(date -u +'%Y%m%dT%H%M%SZ')"
backup_path="$backup_dir/sipad-pre-migrate-$timestamp.dump"
checksum_path="$backup_path.sha256"

cleanup_partial() {
  rm -f -- "$backup_path" "$checksum_path"
}
trap cleanup_partial ERR INT TERM

info "Creating a consistent pre-migration PostgreSQL custom-format backup"
compose exec -T db sh -ec 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-acl' >"$backup_path"
[[ -s "$backup_path" ]] || die "Backup is empty"
(cd "$backup_dir" && sha256sum "$(basename "$backup_path")" >"$(basename "$checksum_path")")
chmod 600 "$backup_path" "$checksum_path"
trap - ERR INT TERM

info "Backup created and checksummed; copy it to approved external encrypted storage before migration"
printf '%s\n' "$backup_path"
