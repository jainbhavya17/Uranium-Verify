"""Private server-side Supabase storage. Requires the existing httpx dependency."""

import hmac
import os
import re
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .storage import LocalPrivateStorage


class SupabasePrivateStorage:
    adapter_name = "private-supabase"
    max_bytes = 32 * 1024 * 1024
    cache_bytes = 512 * 1024 * 1024

    def __init__(self, root: Path, *, client=None):
        url = os.getenv("SUPABASE_URL", "").rstrip("/")
        secret = os.getenv("SUPABASE_SECRET_KEY", "")
        self.bucket = os.getenv("SUPABASE_STORAGE_BUCKET", "")
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or not (parsed.hostname or "").endswith(".supabase.co")
            or parsed.username or parsed.password or parsed.port
            or parsed.path or parsed.query or parsed.fragment
        ):
            raise ValueError("SUPABASE_URL must be your HTTPS Supabase project URL")
        if not secret.startswith("sb_secret_"):
            raise ValueError("SUPABASE_SECRET_KEY must be a server-side secret key")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,62}", self.bucket):
            raise ValueError("Invalid SUPABASE_STORAGE_BUCKET")
        self.base_url = url + "/storage/v1"
        self.headers = {"apikey": secret}
        self.client = client or httpx.Client(timeout=60, follow_redirects=False)
        # Never read the original local directory as a cloud cache: stale local
        # files must not conceal missing cloud originals during migration.
        self.cache = LocalPrivateStorage(Path(root) / "supabase-cache")
        self.root = self.cache.root
        self.lock = threading.Lock()
        self.verify_bucket()

    def _request(self, method, route, **kwargs):
        headers = {**self.headers, **kwargs.pop("headers", {})}
        try:
            return self.client.request(method, self.base_url + route, headers=headers, **kwargs)
        except httpx.HTTPError:
            raise RuntimeError("Supabase Storage connection failed") from None

    @staticmethod
    def _error(response):
        try:
            data = response.json()
            return str(data.get("code", "")), str(data.get("error", ""))
        except (ValueError, AttributeError):
            return "", ""

    def verify_bucket(self):
        response = self._request("GET", "/bucket/" + self.bucket)
        if response.status_code != 200:
            raise RuntimeError(f"Private bucket check failed (HTTP {response.status_code})")
        try:
            data = response.json()
            valid = data.get("public") is False and data.get("id") == self.bucket
        except (ValueError, AttributeError):
            valid = False
        if not valid:
            raise RuntimeError("Configured storage bucket must exist and remain private")

    def read(self, key: str):
        self.cache.path(key)  # Validate opaque object key before making a request.
        route = "/object/authenticated/" + self.bucket + "/" + key
        try:
            with self.client.stream("GET", self.base_url + route, headers=self.headers) as response:
                if response.status_code != 200:
                    response.read()
                    code, error = self._error(response)
                    if response.status_code == 404 or code in {"NoSuchKey", "not_found"} or error == "not_found":
                        raise FileNotFoundError("Private storage object unavailable")
                    raise RuntimeError(f"Private download failed (HTTP {response.status_code})")
                result = bytearray()
                for chunk in response.iter_bytes():
                    if len(result) + len(chunk) > self.max_bytes:
                        raise ValueError("Storage object exceeds the 32 MiB adapter limit")
                    result.extend(chunk)
                return bytes(result)
        except httpx.HTTPError:
            raise RuntimeError("Supabase Storage download failed") from None

    def write_once(self, key: str, content: bytes):
        self.cache.path(key)
        if len(content) > self.max_bytes:
            raise ValueError("Storage object exceeds the 32 MiB adapter limit")
        response = self._request(
            "POST", "/object/" + self.bucket + "/" + key,
            content=content,
            headers={"Content-Type": "application/octet-stream", "x-upsert": "false"},
        )
        if response.status_code in {200, 201}:
            return
        code, error = self._error(response)
        if response.status_code in {400, 409} and (
            code in {"KeyAlreadyExists", "ResourceAlreadyExists"} or error == "Duplicate"
        ):
            if not hmac.compare_digest(self.read(key), content):
                raise ValueError("Immutable storage object conflict")
            return
        raise RuntimeError(f"Private upload failed (HTTP {response.status_code})")

    def path(self, key: str):
        # Processing still needs a private disk path. Originals stay in Supabase.
        target = self.cache.path(key)
        with self.lock:
            if target.exists():
                return target
            content = self.read(key)
            usage = sum(p.stat().st_size for p in self.root.iterdir() if p.is_file())
            if usage + len(content) > self.cache_bytes:
                raise RuntimeError("Private processing cache is full; clear disposable working copies while API and worker are stopped")
            descriptor, temporary = tempfile.mkstemp(prefix=".download-", dir=self.root)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(content)
                os.replace(temporary, target)
            finally:
                Path(temporary).unlink(missing_ok=True)
        return target


def storage_for_settings(settings):
    backend = os.getenv("STORAGE_BACKEND", "local")
    if backend == "local":
        return LocalPrivateStorage(settings.storage_root)
    if backend == "supabase":
        return SupabasePrivateStorage(settings.storage_root)
    raise ValueError("STORAGE_BACKEND must be local or supabase")
