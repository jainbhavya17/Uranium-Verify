import os
from dataclasses import dataclass, field
from pathlib import Path


def load_local_environment():
    # Minimal KEY=value loader: no interpolation or evaluation. Explicit env always wins.
    root = Path(__file__).resolve().parents[3]
    source = root / ".env"
    if source.exists():
        for line in source.read_text(encoding="utf-8-sig").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                if key.strip() in {
                    "APP_ENV",
                    "AUTH_ADAPTER",
                    "DATABASE_URL",
                    "DATABASE_SCHEMA",
                    "CORS_ALLOWED_ORIGINS",
                    "STORAGE_ROOT",
                    "STORAGE_BACKEND",
                    "SUPABASE_URL",
                    "SUPABASE_SECRET_KEY",
                    "SUPABASE_STORAGE_BUCKET",
                    "DEMO_PASSWORD",
                    "PHASE4_DEMO_PASSWORD",
                    "LOCAL_RECOVERY_PREVIEW",
                    "RAG_EMBEDDINGS_ENABLED",
                    "RAG_MODEL_CACHE",
                    "C2PA_TRUST_ANCHORS",
                    "PDF_TRUST_ANCHORS",
                    "SESSION_TTL_SECONDS",
                    "PREVIEW_TTL_SECONDS",
                    "COOKIE_SECURE",
                    "MALWARE_SCANNER",
                    "CLAMSCAN_PATH",
                    "CLAMAV_DATABASE",
                    "TESSERACT_PATH",
                    "OCR_LANGUAGE",
                    "UPLOAD_PDF_MB",
                    "UPLOAD_IMAGE_MB",
                    "UPLOAD_MAX_PAGES",
                    "UPLOAD_MAX_FILES",
                }:
                    os.environ.setdefault(key.strip(), value.strip())


load_local_environment()


@dataclass
class Settings:
    cors_allowed_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            origin.strip().rstrip("/")
            for origin in os.getenv(
                "CORS_ALLOWED_ORIGINS",
                "https://uraniumverify.vercel.app,http://localhost:5173,http://127.0.0.1:5173,"
                "http://localhost:5174,http://127.0.0.1:5174,http://localhost:5184,http://127.0.0.1:5184",
            ).split(",")
            if origin.strip()
        )
    )
    environment: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    auth_adapter: str = field(default_factory=lambda: os.getenv("AUTH_ADAPTER", "demo"))
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./var/uranium.db"))
    storage_root: Path = field(default_factory=lambda: Path(os.getenv("STORAGE_ROOT", "var/private")))
    session_ttl: int = field(default_factory=lambda: int(os.getenv("SESSION_TTL_SECONDS", "3600")))
    preview_ttl: int = field(default_factory=lambda: int(os.getenv("PREVIEW_TTL_SECONDS", "60")))
    cookie_secure: bool = field(default_factory=lambda: os.getenv("COOKIE_SECURE", "false").lower() == "true")

    def validate(self):
        from urllib.parse import urlsplit

        for origin in self.cors_allowed_origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or "*" in origin
                or parsed.path
                or parsed.query
                or parsed.fragment
                or parsed.username
                or parsed.password
            ):
                raise RuntimeError("CORS_ALLOWED_ORIGINS must contain exact HTTP(S) origins")
        if self.environment not in {"development", "test"} or self.auth_adapter != "demo":
            raise RuntimeError(
                "Only the isolated development/test auth adapter is implemented. Production is disabled."
            )
        if self.session_ttl <= 0 or self.preview_ttl <= 0:
            raise RuntimeError("Token lifetimes must be positive")
