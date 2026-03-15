#!/usr/bin/env python3
"""Bootstrap local dependencies for print-cards."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
GUI_DIR = ROOT / "gui"
VENV_DIR = ROOT / ".venv"


def run(cmd: list[str], cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


def venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def venv_bin(venv_dir: Path, executable: str) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / f"{executable}.exe"
    return venv_dir / "bin" / executable


def ensure_venv(venv_dir: Path) -> Path:
    python_path = venv_python(venv_dir)
    if python_path.exists():
        return python_path

    print(f"Creating virtual environment in {venv_dir}")
    venv.EnvBuilder(with_pip=True).create(venv_dir)
    return python_path


def install_cli(python_path: Path, editable: bool) -> None:
    print("Installing Python CLI dependencies")
    run([str(python_path), "-m", "pip", "install", "--upgrade", "pip"])
    install_args = ["-e", ".[dev]"] if editable else ["."]
    run([str(python_path), "-m", "pip", "install", *install_args], cwd=ROOT)


def install_gui() -> None:
    npm = shutil.which("npm")
    if not npm:
        raise SystemExit("npm not found. Install Node.js 18+ to set up the GUI.")

    print("Installing Electron GUI dependencies")
    run([npm, "install"], cwd=GUI_DIR)


def print_next_steps(cli_enabled: bool, gui_enabled: bool) -> None:
    print("\nSetup complete.")
    if os.name == "nt":
        print(f"Activate in PowerShell: {VENV_DIR / 'Scripts' / 'Activate.ps1'}")
    else:
        print(f"Activate in bash/zsh: source {VENV_DIR / 'bin' / 'activate'}")
        print(f"Activate in fish: source {VENV_DIR / 'bin' / 'activate.fish'}")
    if cli_enabled:
        print(f"Run the CLI: {venv_bin(VENV_DIR, 'print-cards')}")
    if gui_enabled:
        print(f"Run the GUI: cd {GUI_DIR} && npm start")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a local virtualenv and install print-cards CLI/GUI dependencies."
    )
    parser.add_argument(
        "--skip-cli",
        action="store_true",
        help="Skip installation of the Python CLI package.",
    )
    parser.add_argument(
        "--skip-gui",
        action="store_true",
        help="Skip installation of the Electron GUI dependencies.",
    )
    parser.add_argument(
        "--editable",
        action="store_true",
        help="Install the Python package in editable mode.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.skip_cli and args.skip_gui:
        print("Nothing to do: both CLI and GUI installation were skipped.")
        return 0

    python_path = ensure_venv(VENV_DIR)

    if not args.skip_cli:
        install_cli(python_path, editable=args.editable)
    if not args.skip_gui:
        install_gui()

    print_next_steps(cli_enabled=not args.skip_cli, gui_enabled=not args.skip_gui)
    return 0


if __name__ == "__main__":
    sys.exit(main())
