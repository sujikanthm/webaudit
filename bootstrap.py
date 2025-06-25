# bootstrap.py
import subprocess
import sys
from pathlib import Path

# Path to a flag file to indicate setup has been completed
setup_complete_flag = Path("./.setup_complete")

def install():
    """
    Runs the necessary setup commands for installing Lighthouse and Playwright browsers.
    Creates a flag file to ensure it only runs once per deployment.
    """
    print("--- Starting one-time setup ---")
    
    try:
        # Install Lighthouse globally using npm
        print("COMMAND: npm install -g lighthouse")
        subprocess.run(
            "npm install -g lighthouse",
            shell=True,  # shell=True is often necessary for npm
            check=True,
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        print("--- Lighthouse installed successfully ---")

        # Install Playwright browsers using the Python module invocation
        print("COMMAND: python -m playwright install")
        subprocess.run(
            [sys.executable, "-m", "playwright", "install"],  # <-- THIS IS THE KEY CHANGE
            check=True,
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        print("--- Playwright browsers installed successfully ---")

        # Create the flag file to indicate setup is done
        setup_complete_flag.touch()
        print("--- One-time setup complete, flag file created ---")

    except subprocess.CalledProcessError as e:
        print(f"!!! SETUP FAILED: A command returned a non-zero exit code: {e.returncode} !!!", file=sys.stderr)
        print(f"!!! Command was: {e.cmd} !!!", file=sys.stderr)
        # Exit with a non-zero code to make the Streamlit deployment fail loudly
        sys.exit(1)
    except Exception as e:
        print(f"!!! SETUP FAILED: An unexpected error occurred: {e} !!!", file=sys.stderr)
        sys.exit(1)

def run_setup():
    """
    Checks if the setup has been run and executes it if not.
    """
    if not setup_complete_flag.exists():
        install()
    else:
        print("--- Setup has already been completed. Skipping. ---")