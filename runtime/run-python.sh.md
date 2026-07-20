#!/usr/bin/env sh
set -eu

if command -v python3 >/dev/null 2>&1 \
  && python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 9))' >/dev/null 2>&1; then
  exec python3 "$@"
fi

if command -v python >/dev/null 2>&1 \
  && python -c 'import sys; raise SystemExit(sys.version_info < (3, 9))' >/dev/null 2>&1; then
  exec python "$@"
fi

if command -v py >/dev/null 2>&1 \
  && py -3 -c 'import sys; raise SystemExit(sys.version_info < (3, 9))' >/dev/null 2>&1; then
  exec py -3 "$@"
fi

printf '%s\n' 'ERROR: Python 3.9+ was not found.' >&2
exit 2
