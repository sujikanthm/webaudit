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
    
    # Install Lighthouse globally using npm
    print("Installing Lighthouse...")
    # Using shell=True is often necessary for npm global installs in non-interactive environments
    try:
        subprocess.run(
            "npm install -g lighthouse",
            shell=True,
            check=True,
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        print("Lighthouse installed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error installing Lighthouse: {e}")
        # Decide if you want to exit or continue
        # sys.exit(1) 

    # Install Playwright browsers
    print("Installing Playwright browsers...")
    try:
        subprocess.run(
            "playwright install",
            shell=True,
            check=True,
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        print("Playwright browsers installed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error installing Playwright browsers: {e}")
        # sys.exit(1)

    # Create the flag file to indicate setup is done
    setup_complete_flag.touch()
    print("--- One-time setup complete ---")

def run_setup():
    """
    Checks if the setup has been run and executes it if not.
    """
    if not setup_complete_flag.exists():
        install()
    else:
        print("Setup has already been completed. Skipping.")