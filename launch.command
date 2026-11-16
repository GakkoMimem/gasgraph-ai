#!/bin/bash
set -e
cd "$(dirname "$0")"
printf '\n  GasGraph AI — synthetic network intelligence demo\n  Opens at http://127.0.0.1:8765\n  Press Ctrl+C to stop.\n\n'
(sleep 1; open 'http://127.0.0.1:8765' >/dev/null 2>&1 || true) &
exec python3 -m gasgraph.server
