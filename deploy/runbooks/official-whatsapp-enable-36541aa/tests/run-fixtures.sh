#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

# This harmless local harness executes only refusal stubs and local inspection.
for script in lib.sh 01-stage.sh 02-activate.sh 03-single-send.sh 04-rollback.sh; do
  set +e
  output="$(env -i PATH="$PATH" bash "$ROOT/$script" 2>&1)"
  status=$?
  set -e
  [[ $status -eq 4 ]] || fail "$script did not refuse with exit 4"
  [[ "$output" == *'REFUSED:'* && "$output" == *'README.md'* && "$output" == *'fresh '* ]] || fail "$script did not direct fresh authorization to README.md"
done

command_pattern='(^|[^[:alnum:]_])(cu'""'rl|ss'""'h|sc'""'p|rs'""'ync|do'""'cker|ku'""'bectl|sys'""'temctl|ng'""'inx|ps'""'ql|my'""'sql|sql'""'ite3|wg'""'et)([^[:alnum:]_]|$)'
sensitive_pattern='(ht'""'tps?://|Be'""'arer[[:space:]]|Authorization:|BEGIN[[:space:]].*PRIVATE|[[:alpha:]_]+(TO'""'KEN|SE'""'CRET|PASS'""'WORD)=|\+[0-9]{7,})'

if grep -REn --exclude=run-fixtures.sh -- "$command_pattern" "$ROOT"; then
  fail 'unsafe operational command pattern found'
fi
if grep -REn --exclude=run-fixtures.sh -- "$sensitive_pattern" "$ROOT"; then
  fail 'sensitive literal or recipient-shaped value found'
fi

printf 'PASS: refusal stubs and static safety fixtures\n'
