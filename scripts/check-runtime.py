"""Verify the inherited Python lock against the selected environment without changing it."""

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import sys

mismatches = []
for row in Path("requirements.lock").read_text().splitlines():
    if "==" not in row or row.startswith("#"):
        continue
    name, expected = row.split("==", 1)
    try:
        actual = version(name)
    except PackageNotFoundError:
        actual = "not installed"
    if actual != expected:
        mismatches.append(f"{name}: expected {expected}, found {actual}")
if mismatches:
    print("\n".join(mismatches))
    sys.exit(1)
print("All pinned Python packages match requirements.lock.")
