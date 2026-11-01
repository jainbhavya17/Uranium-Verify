"""Fail-closed scanner adapters. Never parse bytes before this boundary."""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class ScanOutcome:
    status: str
    mode: str


class MalwareScanner(Protocol):
    def scan(self, path: Path) -> ScanOutcome: ...


class ClamAVScanner:
    def __init__(self, policy):
        self.policy = policy

    def scan(self, path):
        args = [
            self.policy.clamscan,
            "--no-summary",
            "--stdout",
            "--alert-exceeds-max=yes",
            "--max-filesize=25M",
            "--max-scansize=100M",
            "--max-recursion=8",
        ]
        if self.policy.database:
            args += ["--database", self.policy.database]
        try:
            # Output can contain private content/signature details; never return or log it.
            result = subprocess.run(
                args + [str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=60,
                check=False,
            )
            return ScanOutcome({0: "CLEAN", 1: "INFECTED"}.get(result.returncode, "UNAVAILABLE"), "CLAMAV")
        except (OSError, subprocess.TimeoutExpired):
            return ScanOutcome("UNAVAILABLE", "CLAMAV")


class UnavailableScanner:
    def scan(self, path):
        return ScanOutcome("UNAVAILABLE", "UNAVAILABLE")


class MockTestScanner:
    """Explicit MOCK adapter; no protection or claim of a real clean scan."""

    def scan(self, path):
        data = path.read_bytes()
        return ScanOutcome("INFECTED" if b"MOCK_MALWARE_TEST" in data else "CLEAN", "MOCK_TEST")


def scanner_for(policy):
    return {
        "clamav": lambda: ClamAVScanner(policy),
        "mock-test": MockTestScanner,
        "unavailable": UnavailableScanner,
    }[policy.scanner]()
