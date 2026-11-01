"""Engineering resource policies. These are not regulatory limits."""

import os
from dataclasses import dataclass, field


@dataclass
class ProcessingPolicy:
    pdf_bytes: int = field(default_factory=lambda: int(os.getenv("UPLOAD_PDF_MB", "20")) * 1024 * 1024)
    image_bytes: int = field(default_factory=lambda: int(os.getenv("UPLOAD_IMAGE_MB", "10")) * 1024 * 1024)
    pages: int = field(default_factory=lambda: int(os.getenv("UPLOAD_MAX_PAGES", "50")))
    files: int = field(default_factory=lambda: int(os.getenv("UPLOAD_MAX_FILES", "10")))
    pixels: int = 40_000_000
    total_pixels: int = 200_000_000
    timeout: int = 120
    memory_mb: int = 1024
    scanner: str = field(default_factory=lambda: os.getenv("MALWARE_SCANNER", "unavailable"))
    clamscan: str = field(default_factory=lambda: os.getenv("CLAMSCAN_PATH", "clamscan"))
    database: str = field(default_factory=lambda: os.getenv("CLAMAV_DATABASE", ""))
    tesseract: str = field(default_factory=lambda: os.getenv("TESSERACT_PATH", "tesseract"))
    language: str = field(default_factory=lambda: os.getenv("OCR_LANGUAGE", "eng"))
    blur_threshold: float = 12.0
    contrast_threshold: float = 12.0

    def validate(self, environment):
        if self.scanner not in {"unavailable", "clamav", "mock-test"}:
            raise RuntimeError("Unknown scanner adapter")
        if self.scanner == "mock-test" and environment not in {"test", "development"}:
            raise RuntimeError("Mock scanning requires an isolated test/demo environment")
        if min(self.pdf_bytes, self.image_bytes, self.pages) <= 0 or self.pages > 50:
            raise RuntimeError("Invalid upload resource policy")
        if not 1 <= self.files <= 10:
            raise RuntimeError("Upload request file budget must be between one and ten")


PROCESSOR = "p3-pymupdf-tesseract-1"
