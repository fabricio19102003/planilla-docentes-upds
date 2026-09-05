#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/common.sh"

require_command docker
require_command nginx
require_command certbot
require_command ss
require_file "$ENV_FILE"
ensure_private_env

host_port="$(env_value APP_HOST_PORT)"

info "Host and capacity"
uname -a
df -h / /var/lib/docker
free -h

info "Docker runtime"
docker version
docker compose version
docker info --format 'DockerRootDir={{.DockerRootDir}} Driver={{.Driver}}'

info "Read-only network checks"
if ss -H -ltn "sport = :$host_port" | grep -q .; then
  die "APP_HOST_PORT is already listening: $host_port"
fi
ss -H -ltn 'sport = :80 or sport = :443 or sport = :22'

info "Nginx, certificates, firewall, and security services"
sudo nginx -t
sudo certbot certificates
sudo ufw status verbose
systemctl is-active nginx docker fail2ban
systemctl is-enabled nginx docker certbot.timer unattended-upgrades

info "Read-only VPS preflight completed; review certificate expiry, disk headroom, and command output manually"
