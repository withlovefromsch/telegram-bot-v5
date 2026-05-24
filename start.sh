#!/usr/bin/env sh
set -e

# Diagnostic startup script. Writes environment and file listings to persistent /app/data/startup.log
LOG=/app/data/startup.log
echo "=== STARTUP DIAG $(date) ===" > "$LOG"
echo "PWD=$(pwd)" >> "$LOG"
echo "USER=$(whoami 2>/dev/null || echo unknown)" >> "$LOG"
echo "PYTHON=$(which python || which python3 || echo not_found)" >> "$LOG"
echo "PYTHON_VERSION:" >> "$LOG"
(python -V 2>&1 || python3 -V 2>&1) >> "$LOG" 2>&1 || true
echo "ENV:" >> "$LOG"
env >> "$LOG"
echo "ls /app:" >> "$LOG"
ls -la /app >> "$LOG" 2>&1 || echo "cannot list /app" >> "$LOG"
echo "ls project root:" >> "$LOG"
ls -la "$(dirname "$0")" >> "$LOG" 2>&1 || echo "cannot list project root" >> "$LOG"
echo "Print sys.path via python:" >> "$LOG"
python - <<'PY'
import sys, os
try:
    print('\n'.join(sys.path))
except Exception as e:
    print('sys.path error', e)
PY
echo "=== END STARTUP DIAG ===" >> "$LOG"

echo "Starting bot..." >> "$LOG"
exec python /app/bot.py
