#!/bin/bash
set -e

echo "🧹 Cleaning up old environment..."
rm -rf .venv

echo "🐍 Creating new virtual environment..."
python3 -m venv .venv

echo "🔌 Installing dependencies (editable mode)..."
source .venv/bin/activate
pip install --upgrade pip
pip install -e .

echo "✅ Environment setup complete!"
echo "To activate: source .venv/bin/activate"
