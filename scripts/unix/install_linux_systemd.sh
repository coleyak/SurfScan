#!/usr/bin/env bash
# Installs run_collector.py as a systemd --user service: starts
# automatically when you log in, restarts itself if it crashes, and keeps
# running with no terminal window open.
#
# Usage:
#   ./scripts/unix/install_linux_systemd.sh AAPL MSFT SPY
#   INTERVAL=15 MAX_EXPIRIES=6 ./scripts/unix/install_linux_systemd.sh AAPL MSFT SPY
set -euo pipefail

if [ $# -eq 0 ]; then
    echo "Usage: $0 TICKER [TICKER ...]"
    echo "  e.g. $0 AAPL MSFT SPY"
    exit 1
fi

TICKERS="$*"
INTERVAL="${INTERVAL:-15}"
MAX_EXPIRIES="${MAX_EXPIRIES:-6}"
CURRENT_USER="${USER:-$(whoami)}"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
UNIT_DIR="$HOME/.config/systemd/user"
UNIT_NAME="optionsurface-collector.service"
UNIT_FILE="$UNIT_DIR/$UNIT_NAME"

mkdir -p "$UNIT_DIR" "$PROJECT_DIR/logs"
chmod +x "$PROJECT_DIR/scripts/unix/run_collector.sh"

cat > "$UNIT_FILE" <<UNIT_EOF
[Unit]
Description=optionsurface option-chain collector (${TICKERS})
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${PROJECT_DIR}
ExecStart="${PROJECT_DIR}/scripts/unix/run_collector.sh" ${TICKERS} --interval ${INTERVAL} --max-expiries ${MAX_EXPIRIES}
Restart=on-failure
RestartSec=60

[Install]
WantedBy=default.target
UNIT_EOF

systemctl --user daemon-reload
systemctl --user enable --now "$UNIT_NAME"

# Linger is what lets systemd start your user services at boot without an
# active login session -- without it, the service only runs while you're
# actually logged in, which defeats "survives a reboot". Requires sudo;
# you may be prompted for your password.
LINGER_OK=true
if ! sudo loginctl enable-linger "$CURRENT_USER" 2>/dev/null; then
    LINGER_OK=false
fi

echo "Installed and started '${UNIT_NAME}' (systemd --user)."
echo "Tickers: ${TICKERS}   Interval: ${INTERVAL} min   Max expiries: ${MAX_EXPIRIES}"
echo
echo "Watch it work:   journalctl --user -u ${UNIT_NAME} -f"
echo "                 (or: tail -f ${PROJECT_DIR}/logs/collector.log)"
echo "Check status:    systemctl --user status ${UNIT_NAME}"
echo "Stop it:         systemctl --user stop ${UNIT_NAME}"
echo "Disable it:      systemctl --user disable --now ${UNIT_NAME}"
echo
if [ "$LINGER_OK" = true ]; then
    echo "Linger enabled for '$CURRENT_USER' -- this service will start on boot without needing you logged in."
else
    echo "WARNING: couldn't enable linger automatically (needs sudo)."
    echo "Run this yourself, or the service will only run while you're actively logged in:"
    echo "    sudo loginctl enable-linger $CURRENT_USER"
fi
echo
echo "On WSL specifically: linger makes the service start as soon as the WSL VM"
echo "boots, but Windows doesn't boot WSL on its own after a restart -- something"
echo "still needs to trigger that. See scripts/windows/register_wsl_autostart.ps1."