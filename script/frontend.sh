#!/usr/bin/env bash
set -e

export PYTHONPATH="$PWD:$PWD/src"

.venv/bin/gradio src/webapp/app.py --demo-name frontend
