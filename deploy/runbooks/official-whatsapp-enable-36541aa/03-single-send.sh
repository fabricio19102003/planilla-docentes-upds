#!/usr/bin/env bash
set -Eeuo pipefail
printf '%s\n' 'REFUSED: dispatch is non-executable. Read README.md and obtain fresh final-dispatch authorization.' >&2
exit 4
