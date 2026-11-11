#!/bin/bash
# The Pirate Cove - macOS launcher. Created by Ethan Williams 11/9/26
# Double-click to start the site and open it in your browser.
# Keep this window open while using the site; close it to stop.

cd "$(dirname "$0")" || exit 1

if ! venv/bin/python -c 'import flask' >/dev/null 2>&1 || [ ! -f .env ]; then
    echo "The Pirate Cove isn't installed yet. Double-click install.command first."
    read -r -p "Press Return to close this window." _
    exit 1
fi

venv/bin/python scripts/run_local.py
status=$?
if [ $status -ne 0 ]; then
    read -r -p "The site stopped with an error (see above). Press Return to close." _
fi
exit $status
