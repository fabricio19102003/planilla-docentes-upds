#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/common.sh"

"$SCRIPT_DIR/preflight.sh"
info "Building immutable backend and app images"
compose build --pull backend app
info "Checking packaged Nginx configuration"
registry="$(env_value IMAGE_REGISTRY)"
registry="${registry:-local}"
docker run --rm --add-host backend:127.0.0.1 \
  "$registry/sipad-app:$(env_value IMAGE_TAG)" nginx -t
info "Images built for release tag $(env_value IMAGE_TAG)"
