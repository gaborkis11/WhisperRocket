#!/usr/bin/env python3
"""
WhisperRocket - Tailscale detection

The phone endpoint binds to the Tailscale address and to nothing else, so before
it can start we have to know whether Tailscale is actually up and which address
it handed us. That is what this module answers.

Why bind only there: a Tailscale address lives in 100.64.0.0/10 (CGNAT), which is
not routable from the public internet. A packet from outside cannot reach it even
in principle - to talk to the endpoint a device has to be a member of the user's
own tailnet, which the user approves per device. That is the real protection; the
bearer token is the second line, for devices already inside the tailnet.

Every function here is written to answer rather than raise: a missing binary, a
stopped daemon and a garbled response all come back as a state the UI can show.
"""
import ipaddress
import json
import subprocess
from dataclasses import dataclass
from typing import Optional

# Tailscale hands out addresses from the CGNAT range. Checked before binding so a
# misdetection cannot silently put the endpoint on a LAN or public interface.
CGNAT_NETWORK = ipaddress.ip_network("100.64.0.0/10")

# Short on purpose: this runs while the Settings window is being built, and a
# hung daemon must not freeze the UI.
COMMAND_TIMEOUT = 5


@dataclass
class TailscaleState:
    """What we could find out about Tailscale on this machine"""
    running: bool = False
    ipv4: Optional[str] = None
    dns_name: Optional[str] = None
    reason: str = "unknown"      # ok | not_installed | not_running | no_address | unknown

    @property
    def usable(self) -> bool:
        """True when the endpoint has an address it is allowed to bind to"""
        return self.running and bool(self.ipv4)


def is_tailscale_address(address: str) -> bool:
    """True for an address inside Tailscale's CGNAT range"""
    try:
        return ipaddress.ip_address(address) in CGNAT_NETWORK
    except ValueError:
        return False


def _run(args):
    """Run a tailscale command, returning stdout or None. Never raises."""
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT,
            # Closed on purpose: a CLI that finds an open stdin may wait on it.
            # The AI path measured a flat 3 second penalty from exactly this.
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return None
    except Exception:
        return None

    if result.returncode != 0:
        return None
    return result.stdout


def _first_ipv4(addresses) -> Optional[str]:
    """Pick the IPv4 address out of Tailscale's mixed v4/v6 list"""
    for address in addresses or ():
        if is_tailscale_address(address):
            return address
    return None


def get_state() -> TailscaleState:
    """
    Current Tailscale state: is it running, and on which address.

    `tailscale status --json` is the authoritative source because it reports the
    backend state as well as the address - the machine can have a leftover
    address while the daemon is stopped, and binding to that would fail at best
    and listen on a dead interface at worst.
    """
    output = _run(["tailscale", "status", "--json"])
    if output is None:
        # Distinguish "no binary" from "daemon refused", because the Settings
        # window tells the user to install Tailscale in the first case only.
        if _run(["tailscale", "version"]) is None:
            return TailscaleState(reason="not_installed")
        return TailscaleState(reason="not_running")

    try:
        status = json.loads(output)
    except Exception:
        return TailscaleState(reason="unknown")

    if status.get("BackendState") != "Running":
        return TailscaleState(reason="not_running")

    self_node = status.get("Self") or {}
    ipv4 = _first_ipv4(self_node.get("TailscaleIPs"))
    if not ipv4:
        return TailscaleState(running=True, reason="no_address")

    dns_name = (self_node.get("DNSName") or "").rstrip(".") or None
    return TailscaleState(running=True, ipv4=ipv4, dns_name=dns_name, reason="ok")


if __name__ == "__main__":
    state = get_state()
    print(f"running   : {state.running}")
    print(f"ipv4      : {state.ipv4}")
    print(f"dns_name  : {state.dns_name}")
    print(f"reason    : {state.reason}")
    print(f"usable    : {state.usable}")
