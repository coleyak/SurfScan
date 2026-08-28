#!/usr/bin/env bash
# Installs run_collector.py as a macOS LaunchAgent: starts automatically
# when you log in, restarts itself if it crashes, and keeps running with
# no terminal window open -- stops when you log out or the machine sleeps,
# same limitation as the Windows Task Scheduler setup (needs the machine
# actually on and you logged in, screen can be locked).
#
# Usage:
#   ./scripts/unix/install_macos.sh AAPL MSFT SPY
#   INTERVAL=15 MAX_EXPIRIES=6 ./scripts/unix/install_macos.sh AAPL MSFT SPY
set -euo pipefail

if [ $# -eq 0 ]; then
    echo "Usage: $0 TICKER [TICKER ...]"
    echo "  e.g. $0 AAPL MSFT SPY"
    exit 1
fi

TICKERS=("$@")
INTERVAL="${INTERVAL:-15}"
MAX_EXPIRIES="${MAX_EXPIRIES:-6}"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LABEL="com.optionsurface.collector"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
LOG="$PROJECT_DIR/logs/collector.log"

mkdir -p "$PROJECT_DIR/logs" "$HOME/Library/LaunchAgents"
chmod +x "$PROJECT_DIR/scripts/unix/run_collector.sh"

TICKER_XML=""
for t in "${TICKERS[@]}"; do
    TICKER_XML+="        <string>${t}</string>
"
done

cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PROJECT_DIR}/scripts/unix/run_collector.sh</string>
${TICKER_XML}        <string>--interval</string>
        <string>${INTERVAL}</string>
        <string>--max-expiries</string>
        <string>${MAX_EXPIRIES}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${PROJECT_DIR}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>StandardOutPath</key>
    <string>${LOG}</string>
    <key>StandardErrorPath</key>
    <string>${LOG}</string>
</dict>
</plist>
PLIST_EOF

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo "Installed and started LaunchAgent '${LABEL}'."
echo "Tickers: ${TICKERS[*]}   Interval: ${INTERVAL} min   Max expiries: ${MAX_EXPIRIES}"
echo
echo "Watch it work:   tail -f '${LOG}'"
echo "Check status:    launchctl list | grep ${LABEL}"
echo "Stop it:         launchctl unload '${PLIST}'"
echo "Remove entirely: launchctl unload '${PLIST}' && rm '${PLIST}'"
