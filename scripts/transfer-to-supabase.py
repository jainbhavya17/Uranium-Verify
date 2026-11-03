"""Copy DB-referenced originals to private Supabase Storage, preserving all local files."""

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services/api"))

from sqlalchemy import select
from uranium.config import Settings
from uranium.db import make_engine
from uranium.models import DocumentVersion, ReportSnapshot, ReportPublication
from uranium.storage import LocalPrivateStorage
from uranium.supabase_storage import SupabasePrivateStorage


def main():
    settings = Settings()
    source = LocalPrivateStorage(settings.storage_root)
    engine = make_engine(settings.database_url)
    expected = {}
    try:
        with engine.connect() as connection:
            for key, checksum in connection.execute(select(DocumentVersion.storage_key, DocumentVersion.sha256)):
                expected[key] = checksum
            for model in (ReportSnapshot, ReportPublication):
                for key, manifest in connection.execute(select(model.storage_key, model.manifest)):
                    checksum = manifest.get("pdf_sha256")
                    if not checksum:
                        raise ValueError("Report has no recorded integrity checksum")
                    if key in expected and expected[key] != checksum:
                        raise ValueError("Conflicting database integrity records")
                    expected[key] = checksum
        # Validate every original before starting any network uploads.
        for key, checksum in expected.items():
            if hashlib.sha256(source.read(key)).hexdigest() != checksum:
                raise ValueError("Local file failed database integrity verification")
        destination = SupabasePrivateStorage(settings.storage_root)
        for index, (key, checksum) in enumerate(sorted(expected.items()), 1):
            content = source.read(key)
            destination.write_once(key, content)
            if hashlib.sha256(destination.read(key)).hexdigest() != checksum:
                raise ValueError("Cloud round-trip integrity verification failed")
            print(f"Verified {index}/{len(expected)} objects", flush=True)
        print(f"Transfer complete: {len(expected)} originals verified. Local files and database unchanged.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Transfer stopped:", type(error).__name__)
        # Only intentional, sanitized messages; never echo provider exceptions or URLs.
        if type(error) in {ValueError, RuntimeError, FileNotFoundError}:
            print(str(error))
        sys.exit(1)
