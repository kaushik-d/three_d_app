#!/usr/bin/env python3
"""
Launcher script for the 3D CAD Viewer application.
Handles dependency checking and provides helpful startup messages.
"""

import sys
import subprocess


def check_dependencies():
    """Check if required dependencies are installed."""
    missing = []

    try:
        import trame
    except ImportError:
        missing.append("trame")

    try:
        import trame_vuetify
    except ImportError:
        missing.append("trame-vuetify")

    try:
        import trame_vtk
    except ImportError:
        missing.append("trame-vtk")

    try:
        import vtk
    except ImportError:
        missing.append("vtk")

    try:
        import numpy
    except ImportError:
        missing.append("numpy")

    return missing


def install_dependencies():
    """Install missing dependencies."""
    print("\nInstalling dependencies...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
        )
        return True
    except subprocess.CalledProcessError:
        return False


def main():
    """Main entry point."""
    print("\n" + "=" * 60)
    print("  3D CAD Viewer - Startup Check")
    print("=" * 60)

    # Check dependencies
    missing = check_dependencies()

    if missing:
        print(f"\nMissing dependencies: {', '.join(missing)}")
        print("\nWould you like to install them now? [Y/n] ", end="")

        try:
            response = input().strip().lower()
        except EOFError:
            response = "y"

        if response in ("", "y", "yes"):
            if install_dependencies():
                print("\nDependencies installed successfully!")
            else:
                print("\nFailed to install dependencies.")
                print("Please run: pip install -r requirements.txt")
                sys.exit(1)
        else:
            print("\nPlease install dependencies manually:")
            print("  pip install -r requirements.txt")
            sys.exit(1)

    print("\nStarting 3D CAD Viewer...")
    print("-" * 60)

    # Import and run the app
    from app import server

    server.start()


if __name__ == "__main__":
    main()
