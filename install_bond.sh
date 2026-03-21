#!/usr/bin/env bash
set -e

echo "🐕 Installing Bond (system dependencies)..."

sudo apt update
sudo apt install -y \
  python3 python3-pip python3-venv \
  python3-tk \
  ffmpeg \
  portaudio19-dev \
  libopenblas-dev liblapack-dev \
  v4l-utils

echo "🐍 Creating Python venv..."
python3 -m venv bond-env
source bond-env/bin/activate

echo "📦 Installing Python dependencies..."
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

echo "✅ Install complete."
echo ""
echo "NEXT:"
echo "  1) Ensure your Vosk model folder exists (e.g. ./vosk-model-small-en-us-0.15)"
echo "  2) Run: source bond-env/bin/activate && python main.py"
