#!/usr/bin/env python3
"""Launch the doc-digest chat server.

Usage:
    python start_server.py <server_dir> [--port PORT]

The server_dir must contain:
  - server.py
  - document_data.json
"""

import argparse
import subprocess
import sys
from pathlib import Path


def start_server(server_dir: str, port: int = 8765) -> None:
    """Set up and start the chat server."""
    server_path = Path(server_dir)

    # Validate required files
    required_files = ["server.py", "document_data.json", "agent.py", "tools.py", "models.py"]
    missing = [f for f in required_files if not (server_path / f).exists()]
    if missing:
        print(f"Error: Missing required files in {server_dir}:")
        for f in missing:
            print(f"  - {f}")
        sys.exit(1)

    requirements = server_path / "requirements.txt"
    venv_path = server_path / ".venv"

    # Create venv and install deps if needed
    if not venv_path.exists():
        print("Setting up virtual environment...")
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_path)],
            check=True,
        )

    pip = str(venv_path / "bin" / "pip")
    python = str(venv_path / "bin" / "python")

    if requirements.exists():
        print("Installing dependencies...")
        subprocess.run(
            [pip, "install", "-q", "-r", str(requirements)],
            check=True,
        )

    # Start the server
    print(f"\nStarting doc-digest chat server on http://localhost:{port}")
    print("Press Ctrl+C to stop.\n")

    try:
        subprocess.run(
            [
                python, "-m", "uvicorn",
                "server:app",
                "--host", "0.0.0.0",
                "--port", str(port),
                "--reload",
            ],
            cwd=str(server_path),
            check=True,
        )
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start doc-digest chat server")
    parser.add_argument("server_dir", help="Path to server directory")
    parser.add_argument("--port", type=int, default=8765, help="Port (default: 8765)")
    args = parser.parse_args()

    start_server(args.server_dir, args.port)
