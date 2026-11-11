#!/bin/bash
# The Pirate Cove - macOS installer. Created by Ethan Williams 11/9/26
# Double-click this file (the first time: right-click > Open, then Open).
# It makes a Python virtual environment (venv/), installs the requirements,
# writes .env, sets up the PostgreSQL tables and offers to create an admin.
# Safe to run again.

cd "$(dirname "$0")" || exit 1
echo "=== The Pirate Cove installer ==="

finish() {
    echo
    read -r -p "Press Return to close this window." _
    exit "$1"
}

# Find Python 3.10 or newer (newest first)
PY=""
for cmd in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" >/dev/null 2>&1 && \
       "$cmd" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
        PY="$(command -v "$cmd")"
        break
    fi
done

if [ -z "$PY" ]; then
    echo "Python 3.10 or newer is needed."
    if command -v brew >/dev/null 2>&1; then
        read -r -p "Install it with Homebrew now? (Y/n) " answer
        if [ -z "$answer" ] || [[ "$answer" =~ ^[Yy] ]]; then
            brew install python@3.12 && PY="$(brew --prefix)/bin/python3.12"
        fi
    fi
    if [ -z "$PY" ]; then
        echo "Install Python from https://www.python.org/downloads/ and run this installer again."
        open "https://www.python.org/downloads/"
        finish 1
    fi
fi
echo "Using $("$PY" --version) at $PY"

# Make (or repair) the virtual environment
if ! venv/bin/python -c 'import sys' >/dev/null 2>&1; then
    echo "Creating the virtual environment (venv/)..."
    rm -rf venv
    "$PY" -m venv venv || { echo "Could not create venv."; finish 1; }
fi

echo "Installing requirements (this can take a minute)..."
venv/bin/python -m pip install --quiet --upgrade pip
venv/bin/python -m pip install --quiet -r requirements.txt || { echo "Installing requirements failed."; finish 1; }

venv/bin/python scripts/install_helper.py || { echo; echo "Setup did not finish. Fix the problem above and run the installer again."; finish 1; }

chmod +x "Launch Pirate Cove.command" 2>/dev/null
echo
echo "Done! Double-click \"Launch Pirate Cove.command\" to start the site."
finish 0
