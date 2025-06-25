#!/bin/bash

# This script is run by the Streamlit app before it starts.
# It installs non-Python dependencies.

# Exit immediately if a command exits with a non-zero status.
set -e

# The flag file to check if setup has been done
# Note: The path must be in a writable directory. /home/appuser/ is a good choice.
SETUP_FLAG="/home/appuser/.setup_complete"

if [ ! -f "$SETUP_FLAG" ]; then
    echo "--- First time setup: Installing Lighthouse and Playwright browsers ---"

    # Install Lighthouse globally
    npm install -g lighthouse

    # Install Playwright's browser binaries
    python -m playwright install

    # Create the flag file
    touch "$SETUP_FLAG"
    echo "--- Setup complete. Flag file created. ---"
else
    echo "--- Setup already complete. Skipping. ---"
fi

# Now, execute the command passed to the script (which will be `streamlit run app.py`)
exec "$@"