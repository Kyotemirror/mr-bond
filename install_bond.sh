#!/bin/bash
set -e

echo "🐕 Installing Bond dependencies..."

# System deps
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
  python3 python3-pip python3-venv \
  ffmpeg portaudio19-dev \
  libatlas-base-dev libopenblas-dev liblapack-dev \
  v4l-utils i2c-tools

# Python env
python3 -m venv bond-env
source bond-env/bin/activate

pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

echo "✅ Bond installation complete"
