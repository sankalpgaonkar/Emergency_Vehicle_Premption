#!/usr/bin/env bash
# Exit on error
set -o errexit

pip install --upgrade pip
# Install lightweight CPU-only PyTorch (crucial to avoid 512MB RAM OOM during build)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r demo_app/requirements.txt

