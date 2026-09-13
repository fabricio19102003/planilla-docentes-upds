#!/usr/bin/env bash
set -Eeuo pipefail
printf '%s\n' 'REFUSED: staging is non-executable. Read README.md and obtain fresh deployment authorization.' >&2
exit 4
