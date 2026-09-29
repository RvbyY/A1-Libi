#!/usr/bin/env bash
set -e

echo "[+] Creating virtual environment..."
python3 -m venv .venv

echo "[+] Installing dependencies..."
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

if [ ! -f .env ]; then
    echo "[+] Creating .env from .env.exemple..."
    cp .env.exemple .env
else
    echo "[*] .env already exists."
fi

echo
echo "[✓] Setup complete."
echo
echo "Start the backend with:"
echo "  ./backend.sh"
echo
echo "Then run the CLI with:"
echo '  env PYTHONPATH="$PWD:$PWD/src" .venv/bin/python src/main.py'