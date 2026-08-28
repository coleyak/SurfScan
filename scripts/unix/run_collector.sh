#!/usr/bin/env bash
# Thin wrapper around run_collector.py: forces unbuffered output (so the
# log file updates in real time instead of in delayed buffered chunks --
# stdout buffering kicks in automatically once it's not a real terminal,
# same issue as the Windows Task Scheduler setup) and appends to a log
# file, since there's no console attached for print() to reach.
#
# Not meant to be run directly day-to-day -- install_macos.sh and
# install_linux_systemd.sh both point their background job at this script.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_DIR"
mkdir -p logs

PYTHON_BIN="${PYTHON_BIN:-python3}"

exec "$PYTHON_BIN" -u scripts/run_collector.py "$@" >> logs/collector.log 2>&1
