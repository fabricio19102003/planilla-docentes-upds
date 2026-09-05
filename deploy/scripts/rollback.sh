#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/common.sh"

require_command curl
require_file "$ENV_FILE"
ensure_private_env

previous_tag="${1:-}"
if [[ -z "$previous_tag" && -f "$STATE_DIR/previous-release" ]]; then
  previous_tag="$(cat "$STATE_DIR/previous-release")"
fi
[[ -n "$previous_tag" && "$previous_tag" != "latest" ]] || die "Usage: $0 <previous-immutable-image-tag>"

if [[ "${CONFIRM_SCHEMA_COMPATIBLE:-}" != "YES" ]]; then
  die "Image rollback is blocked. Set CONFIRM_SCHEMA_COMPATIBLE=YES only after proving the current DB schema is compatible. Destructive migrations require a separately approved restore."
fi

info "Creating a safety backup of the current database before image rollback"
"$SCRIPT_DIR/backup.sh"

registry="$(env_value IMAGE_REGISTRY)"
registry="${registry:-local}"
for image in "$registry/sipad-backend:$previous_tag" "$registry/sipad-app:$previous_tag"; do
  docker image inspect "$image" >/dev/null 2>&1 || die "Rollback image is not present locally: $image"
done

info "Rolling application containers back to image tag $previous_tag without changing the database"
compose stop app backend >/dev/null 2>&1 || true
IMAGE_TAG="$previous_tag" docker compose --env-file "$ENV_FILE" --file "$COMPOSE_FILE" up --detach --no-build backend app

wait_for_healthy backend 60
wait_for_healthy app 30
host_port="$(env_value APP_HOST_PORT)"
curl --fail --silent --show-error --max-time 10 "http://127.0.0.1:$host_port/ready" >/dev/null

printf '%s\n' "$previous_tag" >"$STATE_DIR/current-release"
chmod 600 "$STATE_DIR/current-release"
info "Image rollback completed; update IMAGE_TAG in the protected environment file before the next Compose operation"
