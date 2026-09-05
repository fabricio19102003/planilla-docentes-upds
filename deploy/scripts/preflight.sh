#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/common.sh"

require_command docker
require_command git
require_file "$ENV_FILE"
require_file "$COMPOSE_FILE"
require_file "$REPO_ROOT/normalizar_horarios.py"
require_file "$REPO_ROOT/backend/data/assets/logo_upds.png"
ensure_private_env

docker compose version >/dev/null
docker info >/dev/null

if [[ "${SKIP_GIT_CLEAN_CHECK:-0}" != "1" ]] && [[ -n "$(git -C "$REPO_ROOT" status --porcelain --untracked-files=normal)" ]]; then
  die "Repository is dirty. Deploy only an immutable reviewed commit, or set SKIP_GIT_CLEAN_CHECK=1 for an explicit non-production inspection."
fi

required_keys=(IMAGE_TAG APP_HOST_PORT POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD CORS_ORIGINS JWT_SECRET DOCENTE_DEFAULT_PASSWORD)
for key in "${required_keys[@]}"; do
  value="$(env_value "$key")"
  [[ -n "$value" ]] || die "$key is empty or missing in $ENV_FILE"
  [[ "$value" != *'<'* && "$value" != *'>'* && "$value" != *'CHANGE_ME'* ]] || die "$key still contains a placeholder"
done

image_tag="$(env_value IMAGE_TAG)"
[[ "$image_tag" != "latest" ]] || die "IMAGE_TAG=latest is forbidden; use an immutable release tag"

host_port="$(env_value APP_HOST_PORT)"
[[ "$host_port" =~ ^[0-9]+$ ]] || die "APP_HOST_PORT must be numeric"
(( host_port >= 1024 && host_port <= 65535 )) || die "APP_HOST_PORT must be between 1024 and 65535"

jwt_secret="$(env_value JWT_SECRET)"
(( ${#jwt_secret} >= 64 )) || die "JWT_SECRET must contain at least 64 characters (32 random bytes when hex-encoded)"

postgres_password="$(env_value POSTGRES_PASSWORD)"
(( ${#postgres_password} >= 32 )) || die "POSTGRES_PASSWORD must contain at least 32 characters"
[[ "$postgres_password" =~ ^[A-Za-z0-9._~-]+$ ]] || die "POSTGRES_PASSWORD must be URI-safe because Compose embeds it in DATABASE_URL"

validate_bootstrap_password() {
  local key="$1" required="$2" password
  password="$(env_value "$key")"
  if [[ -z "$password" && "$required" == "false" ]]; then
    return
  fi
  [[ -n "$password" ]] || die "$key is required"
  (( ${#password} >= 16 )) || die "$key must contain at least 16 characters"
  [[ "$password" =~ [[:upper:]] ]] || die "$key must contain an uppercase letter"
  [[ "$password" =~ [[:lower:]] ]] || die "$key must contain a lowercase letter"
  [[ "$password" =~ [[:digit:]] ]] || die "$key must contain a digit"
}

validate_bootstrap_password DOCENTE_DEFAULT_PASSWORD true
validate_bootstrap_password ADMIN_DEFAULT_PASSWORD false

[[ "$(env_value APP_ENV)" == "production" ]] || die "APP_ENV must be production"
[[ "$(env_value AUTO_SCHEMA_BOOTSTRAP)" == "false" ]] || die "AUTO_SCHEMA_BOOTSTRAP must be false in production"

compose config --quiet

if [[ "$(env_value OFFICIAL_WHATSAPP_ENABLED)" == "true" || "$(env_value WHATSAPP_DISPATCH_ENABLED)" == "true" ]]; then
  [[ "$(env_value OFFICIAL_WHATSAPP_ENABLED)" == "true" && "$(env_value WHATSAPP_DISPATCH_ENABLED)" == "true" ]] || die "Official WhatsApp flags must be enabled together"
  official_keys=(TWILIO_ACCOUNT_SID TWILIO_API_KEY_SID TWILIO_API_KEY_SECRET BILLING_MEDIA_PUBLIC_BASE_URL TWILIO_OFFICIAL_FROM TWILIO_OFFICIAL_SENDER_SID TWILIO_OFFICIAL_CONTENT_SID TWILIO_STATUS_CALLBACK_URL TWILIO_INBOUND_CALLBACK_URL TWILIO_AUTH_TOKEN TWILIO_OFFICIAL_MEDIA_MPS TWILIO_OFFICIAL_MOVING_RECIPIENT_LIMIT)
  for key in "${official_keys[@]}"; do
    [[ -n "$(env_value "$key")" ]] || die "$key is required when official WhatsApp dispatch is enabled"
  done
  for key in TWILIO_OFFICIAL_MEDIA_MPS TWILIO_OFFICIAL_MOVING_RECIPIENT_LIMIT; do
    [[ "$(env_value "$key")" =~ ^[1-9][0-9]*(\.[0-9]+)?$ ]] || die "$key must be positive numeric"
  done
  base="$(env_value BILLING_MEDIA_PUBLIC_BASE_URL)"
  [[ "$base" =~ ^https://[A-Za-z0-9.-]+(:[0-9]+)?$ ]] || die "BILLING_MEDIA_PUBLIC_BASE_URL must be a canonical HTTPS origin"
  [[ "$(env_value TWILIO_STATUS_CALLBACK_URL)" == "$base/api/twilio/whatsapp/status" ]] || die "TWILIO_STATUS_CALLBACK_URL must be the canonical status callback"
  [[ "$(env_value TWILIO_INBOUND_CALLBACK_URL)" == "$base/api/twilio/whatsapp/inbound" ]] || die "TWILIO_INBOUND_CALLBACK_URL must be the canonical inbound callback"
fi

info "Preflight passed without exposing environment values"
