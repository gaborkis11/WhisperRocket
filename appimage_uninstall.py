#!/usr/bin/env python3
"""
WhisperRocket AppImage Uninstaller
Removes configuration, downloaded models, and CUDA libraries.
"""

import os
import sys
import shutil
from pathlib import Path


# ANSI color codes
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"


def get_size_human(path):
    """Get directory size in human-readable format."""
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.exists(filepath):
                    total_size += os.path.getsize(filepath)
    except (OSError, PermissionError):
        return "N/A"

    # Convert to human readable
    for unit in ['B', 'K', 'M', 'G']:
        if total_size < 1024.0 or unit == 'G':
            if unit == 'B':
                return f"{total_size}{unit}"
            else:
                return f"{total_size:.1f}{unit}"
        total_size /= 1024.0

    return f"{total_size:.1f}T"


def print_header():
    """Print the uninstaller header."""
    print(f"\n{CYAN}{BOLD}╔══════════════════════════════════════════╗{RESET}")
    print(f"{CYAN}{BOLD}║   WhisperRocket Uninstaller (AppImage)   ║{RESET}")
    print(f"{CYAN}{BOLD}╚══════════════════════════════════════════╝{RESET}\n")


def scan_components():
    """Scan for installed components and return their info."""
    home = Path.home()

    components = {
        "config": {
            "path": home / ".config" / "whisperrocket",
            "description": "Configuration",
            "found": False,
            "size": "0B"
        },
        "models": {
            "path": home / ".cache" / "huggingface" / "hub" / "whisperrocket_models",
            "description": "Downloaded models",
            "found": False,
            "size": "0B"
        },
        "cuda": {
            "path": home / ".local" / "share" / "whisperrocket",
            "description": "CUDA libraries",
            "found": False,
            "size": "0B"
        }
    }

    print(f"{BOLD}Scanning installed components...{RESET}\n")

    for key, info in components.items():
        if info["path"].exists():
            info["found"] = True
            info["size"] = get_size_human(info["path"])
            print(f"  {GREEN}[FOUND]{RESET} {info['description']}: {CYAN}~/{info['path'].relative_to(home)}{RESET} ({YELLOW}{info['size']}{RESET})")
        else:
            print(f"  {RED}[NOT FOUND]{RESET} {info['description']}: {CYAN}~/{info['path'].relative_to(home)}{RESET}")

    return components


def get_user_choice():
    """Get user's choice for uninstall type."""
    print(f"\n{BOLD}What would you like to remove?{RESET}\n")
    print(f"  {GREEN}1){RESET} Full uninstall (config + models + CUDA)")
    print(f"  {YELLOW}2){RESET} Keep models (only remove config + CUDA)")
    print(f"  {RED}3){RESET} Cancel\n")

    while True:
        try:
            choice = input(f"{BOLD}Select [1-3]:{RESET} ").strip()
            if choice in ['1', '2', '3']:
                return int(choice)
            print(f"{RED}Invalid choice. Please enter 1, 2, or 3.{RESET}")
        except (EOFError, KeyboardInterrupt):
            print(f"\n{RED}Cancelled by user.{RESET}")
            return 3


def confirm_full_uninstall():
    """Ask for 'yes' confirmation for full uninstall."""
    print(f"\n{RED}{BOLD}⚠ WARNING: This will remove ALL WhisperRocket data!{RESET}")
    print(f"{YELLOW}This includes configuration, downloaded models, and CUDA libraries.{RESET}")

    try:
        confirmation = input(f"\n{BOLD}Type 'yes' to confirm full uninstall:{RESET} ").strip().lower()
        return confirmation == 'yes'
    except (EOFError, KeyboardInterrupt):
        print(f"\n{RED}Cancelled by user.{RESET}")
        return False


def remove_directory(path, name):
    """Remove a directory and report status."""
    try:
        if path.exists():
            print(f"  {YELLOW}Removing{RESET} {name}...", end=" ")
            shutil.rmtree(path)
            print(f"{GREEN}✓{RESET}")
            return True
        else:
            print(f"  {BLUE}Skipping{RESET} {name} (not found)")
            return False
    except Exception as e:
        print(f"{RED}✗{RESET}")
        print(f"  {RED}Error removing {name}: {e}{RESET}")
        return False


def run_uninstall():
    """Main uninstall function."""
    print_header()

    components = scan_components()

    # Check if anything is installed
    if not any(comp["found"] for comp in components.values()):
        print(f"\n{YELLOW}No WhisperRocket components found. Nothing to uninstall.{RESET}\n")
        return

    choice = get_user_choice()

    if choice == 3:
        print(f"\n{YELLOW}Uninstall cancelled. No changes were made.{RESET}\n")
        return

    # Full uninstall requires confirmation
    if choice == 1:
        if not confirm_full_uninstall():
            print(f"\n{YELLOW}Uninstall cancelled. No changes were made.{RESET}\n")
            return

    print(f"\n{BOLD}Removing components...{RESET}\n")

    removed_count = 0

    # Remove config (both options)
    if components["config"]["found"]:
        if remove_directory(components["config"]["path"], "Configuration"):
            removed_count += 1

    # Remove CUDA libraries (both options)
    if components["cuda"]["found"]:
        if remove_directory(components["cuda"]["path"], "CUDA libraries"):
            removed_count += 1

    # Remove models (only for full uninstall)
    if choice == 1 and components["models"]["found"]:
        if remove_directory(components["models"]["path"], "Downloaded models"):
            removed_count += 1

    # Final message
    print(f"\n{GREEN}{BOLD}✓ Uninstall complete!{RESET}")
    if removed_count > 0:
        print(f"{GREEN}{removed_count} component(s) removed.{RESET}")

    if choice == 2 and components["models"]["found"]:
        print(f"\n{BLUE}ℹ Models were kept at:{RESET} {CYAN}~/{components['models']['path'].relative_to(Path.home())}{RESET}")
        print(f"{BLUE}  Size:{RESET} {YELLOW}{components['models']['size']}{RESET}")

    print(f"\n{YELLOW}To complete uninstall, delete the AppImage file itself.{RESET}\n")


if __name__ == "__main__":
    run_uninstall()
