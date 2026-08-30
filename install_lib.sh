#!/bin/bash
# WhisperRocket installer library - sourced by install.sh, unit-tested by
# tests/test_install_lib.py. Keep this file side-effect free: only function
# definitions, no top-level commands.

# Print the distro ID from os-release (or "unknown").
# Usage: detect_distro_id [os_release_path]
detect_distro_id() {
    local os_release="${1:-${WR_OS_RELEASE:-/etc/os-release}}"
    if [ -f "$os_release" ]; then
        ( . "$os_release" && echo "${ID:-unknown}" )
    else
        echo "unknown"
    fi
}

# Print the package manager for this system: apt|dnf|pacman|zypper|unknown.
# Checks os-release ID first, then each word of ID_LIKE (so derivatives such
# as Omarchy with ID_LIKE=arch resolve correctly), and finally falls back to
# whichever known package manager binary exists. Returns 1 on "unknown".
# Usage: detect_pkg_manager [os_release_path]
detect_pkg_manager() {
    local os_release="${1:-${WR_OS_RELEASE:-/etc/os-release}}"
    local id="" id_like=""
    if [ -f "$os_release" ]; then
        id="$( . "$os_release" && echo "${ID:-}" )"
        id_like="$( . "$os_release" && echo "${ID_LIKE:-}" )"
    fi
    local candidate
    for candidate in $id $id_like; do
        case "$candidate" in
            ubuntu|debian|linuxmint|pop|elementary|zorin)
                echo "apt"; return 0 ;;
            fedora|rhel|centos|rocky|almalinux)
                echo "dnf"; return 0 ;;
            arch|archlinux|manjaro|endeavouros|garuda|omarchy|cachyos)
                echo "pacman"; return 0 ;;
            opensuse*|suse|sles)
                echo "zypper"; return 0 ;;
        esac
    done
    # ID/ID_LIKE unknown - fall back to whichever package manager exists
    command -v apt    >/dev/null 2>&1 && { echo "apt";    return 0; }
    command -v dnf    >/dev/null 2>&1 && { echo "dnf";    return 0; }
    command -v pacman >/dev/null 2>&1 && { echo "pacman"; return 0; }
    command -v zypper >/dev/null 2>&1 && { echo "zypper"; return 0; }
    echo "unknown"
    return 1
}
