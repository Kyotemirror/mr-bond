#!/usr/bin/env bash

# Fail on error
set -e

# Always run from project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🐕 Starting Bond..."

# Check virtual environment
if [ ! -d "bond-env" ]; then
  echo "❌ bond-env not found. Run ./install_bond.sh first."
  exit 1
fi

# Activate venv
source bond-env/bin/activate

# Ensure main exists
if [ ! -f "main.py" ]; then
  echo "❌ main.py not found."
  exit 1
fi

export PYTHONUNBUFFERED=1

python main.py
