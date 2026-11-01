import re
from pathlib import Path


class LocalPrivateStorage:
    """Never mounted as a static/public directory. Objects are immutable and opaque."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key: str):
        if not re.fullmatch(r"[a-f0-9]{64}", key):
            raise ValueError("Invalid storage key")
        target = (self.root / key).resolve()
        if target.parent != self.root:
            raise ValueError("Invalid storage path")
        return target

    def write_once(self, key: str, content: bytes):
        target = self.path(key)
        if target.exists():
            if target.read_bytes() != content:
                raise ValueError("Immutable storage object conflict")
            return
        with target.open("xb") as stream:
            stream.write(content)

    def read(self, key: str):
        return self.path(key).read_bytes()
