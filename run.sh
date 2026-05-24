#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

echo "Installing dependencies for current user..."
python3 -m pip install --user -r requirements.txt

echo "Starting bot..."
export PYTHONPATH="$(pwd)"
python3 -m bot
