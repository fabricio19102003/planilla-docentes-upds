#!/usr/bin/env bash
set -Eeuo pipefail
printf '%s\n' 'REFUSED: rollback is non-executable. Read README.md and obtain fresh rollback authorization.' >&2
exit 4
