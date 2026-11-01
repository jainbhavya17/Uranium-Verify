"""Resource-isolated worker entry point. Document content is data, never instructions.

No DB, application secrets, network clients or model integrations are imported here.
All coordinates are in the ORIGINAL page coordinate space, including rotated OCR.
"""

import csv
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


class Rejected(Exception):
    pass


def normalize(key, raw):
    if key.endswith("date"):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(raw.strip(), fmt).date().isoformat()
            except ValueError:
                pass
        return None
    return re.sub(r"\s+", " ", raw).strip() or None


LABELS = {
    "institution name": "institution_name",
    "permanent id": "permanent_id",
    "address": "address",
    "certificate id": "certificate_id",
    "issue date": "issue_date",
    "expiry date": "expiry_date",
    "academic year": "academic_year",
    "issuer": "issuer",
}
TYPES = {
    "FIRE_SAFETY": "fire safety",
    "COMPLETION": "completion certificate",
    "OCCUPANCY": "occupancy certificate",
    "BUILDING_LICENSE": "building license",
    "FORM_D": "form d",
    "STRUCTURAL_STABILITY": "structural stability",
    "AFFIDAVIT_2": "affidavit 2",
    "PAYMENT_RECEIPT": "payment receipt",
    "SATELLITE_MAP": "satellite map",
    "AUDITED_ACCOUNTS": "audited accounts",
    "AFFIDAVIT_8": "affidavit 8",
    "AFFIDAVIT_7": "affidavit 7",
    "LAND_REGISTRATION": "land registration",
    "FACULTY_LIST": "faculty list",
    "AFFILIATION": "affiliation letter",
    "CLOSURE_RESOLUTION": "closure resolution",
    "FORMAT_3": "format 3",
    "FELLOW_FACULTY": "fellow faculty",
    "GOV_NORMS_LETTER": "government norms",
}


def fields_from_lines(lines, page, method):
    fields = []
    for text, box, confidence in lines:
        for label, key in LABELS.items():
            match = re.match(r"^" + re.escape(label) + r"\s*:\s*(.+)$", text, re.I)
            if match:
                raw = match.group(1)[:500]
                value = normalize(key, raw)
                fields.append(
                    {
                        "field_key": key,
                        "raw": raw,
                        "normalized": value,
                        "page": page,
                        "bbox": box,
                        "confidence": confidence,
                        "method": method,
                        "uncertainty": "UNREADABLE_OR_AMBIGUOUS"
                        if value is None
                        else "OCR_REQUIRES_REVIEW"
                        if method == "TESSERACT"
                        else "DIGITAL_TEXT",
                    }
                )
    return fields


def ocr(image, policy, directory, page):
    import cv2
    import numpy as np

    gray = np.array(image.convert("L"))
    blur, contrast = float(cv2.Laplacian(gray, cv2.CV_64F).var()), float(gray.std())
    if contrast < policy["contrast_threshold"] or blur < policy["blur_threshold"]:
        quality = "MARGINAL"
    else:
        quality = "READABLE"
    candidates = []
    # English printed forms only in this release. Enumerating right-angle rotations avoids
    # claiming arbitrary skew/handwriting or OSD language support.
    for angle in (0, 90, 180, 270):
        rotated = image.rotate(angle, expand=True)
        file = directory / f"page-{page}-{angle}.png"
        rotated.save(file)
        try:
            run = subprocess.run(
                [policy["tesseract"], str(file), "stdout", "-l", policy["language"], "--psm", "6", "tsv"],
                capture_output=True,
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise Rejected("OCR_UNAVAILABLE")
        if run.returncode or len(run.stdout) > 2_000_000:
            raise Rejected("OCR_UNAVAILABLE")
        rows = list(csv.DictReader(io.StringIO(run.stdout.decode("utf-8", errors="replace")), delimiter="\t"))
        groups = {}
        scores = []
        for row in rows:
            text = row.get("text", "").strip()
            confidence = float(row.get("conf", -1))
            if not text or confidence < 0:
                continue
            scores.append(confidence)
            groups.setdefault((row["block_num"], row["par_num"], row["line_num"]), []).append(row)
        lines = []
        for group in groups.values():
            x = min(int(r["left"]) for r in group)
            y = min(int(r["top"]) for r in group)
            right = max(int(r["left"]) + int(r["width"]) for r in group)
            bottom = max(int(r["top"]) + int(r["height"]) for r in group)
            w, h = image.size
            # Inverse Pillow counter-clockwise rotation into original image coordinates.
            points = [(x, y), (right, y), (x, bottom), (right, bottom)]

            def inverse(a, b):
                return {0: (a, b), 90: (w - b, a), 180: (w - a, h - b), 270: (b, h - a)}[angle]

            original = [inverse(a, b) for a, b in points]
            box = [
                min(a for a, b in original),
                min(b for a, b in original),
                max(a for a, b in original),
                max(b for a, b in original),
            ]
            lines.append(
                (
                    " ".join(r["text"] for r in group),
                    box,
                    sum(float(r["conf"]) for r in group) / len(group) / 100,
                )
            )
        score = sum(scores) / max(len(scores), 1)
        # Prefer recognizable label lines over confidently hallucinated sideways tokens.
        recognized = len(fields_from_lines(lines, page, "TESSERACT"))
        candidates.append((recognized * 100 + score, lines, angle, score))
    _, lines, angle, score = max(candidates, key=lambda x: x[0])
    if score < 65 or not lines:
        quality = "UNREADABLE"
    return lines, {
        "blur": round(blur, 2),
        "contrast": round(contrast, 2),
        "quality": quality,
        "rotation": angle,
        "ocr_confidence": round(score / 100, 3),
    }


def parse(path, policy, directory):
    import pymupdf
    from PIL import Image, ImageOps
    import warnings

    Image.MAX_IMAGE_PIXELS = policy["pixels"]
    warnings.simplefilter("error", Image.DecompressionBombWarning)
    data = path.read_bytes()
    pages, fields, texts = [], [], []
    total_pixels = 0
    libraries = {"pymupdf": pymupdf.VersionBind}
    document = None
    if data.startswith(b"%PDF-"):
        try:
            document = pymupdf.open(path)
        except Exception:
            raise Rejected("CORRUPT_FILE")
        if document.needs_pass or document.is_encrypted or document.metadata.get("encryption"):
            raise Rejected("ENCRYPTED_PDF")
        if document.is_repaired:
            raise Rejected("CORRUPT_FILE")
        if not 0 < len(document) <= policy["pages"]:
            raise Rejected("PAGE_LIMIT")
        if document.xref_length() > 100000:
            raise Rejected("RESOURCE_LIMIT")
        if document.embfile_count():
            raise Rejected("UNSAFE_CONTENT")
        for xref in range(1, document.xref_length()):
            value = document.xref_object(xref)
            if re.search(
                r"/(?:JavaScript|JS|Launch|EmbeddedFile|RichMedia|OpenAction|AA|XFA|GoToR|SubmitForm|ImportData|Rendition|3D|Sound|Movie)\b",
                value,
            ):
                raise Rejected("UNSAFE_CONTENT")
        count = len(document)
    else:
        try:
            with Image.open(path) as check:
                if check.width * check.height > policy["pixels"] or getattr(check, "n_frames", 1) != 1:
                    raise Rejected("RESOURCE_LIMIT")
                check.verify()
        except Rejected:
            raise
        except Exception:
            raise Rejected("CORRUPT_FILE")
        count = 1
    for index in range(count):
        number = index + 1
        lines = []
        if document:
            page = document[index]
            if page.rect.width * page.rect.height * (200 / 72) ** 2 > policy["pixels"]:
                raise Rejected("RESOURCE_LIMIT")
            blocks = page.get_text("dict", flags=pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES)[
                "blocks"
            ]
            for block in blocks:
                for line in block.get("lines", []):
                    text = "".join(span["text"] for span in line["spans"])
                    lines.append((text, list(pymupdf.Rect(line["bbox"]) * page.rotation_matrix), 1.0))
            if sum(len(t) for t, _, _ in lines) > 100000:
                raise Rejected("RESOURCE_LIMIT")
            width, height = page.rect.width, page.rect.height
        if sum(len(t.strip()) for t, _, _ in lines) >= 30:
            method, quality = "PYMUPDF", {"quality": "DIGITAL_TEXT", "rotation": 0}
        else:
            if document:
                pix = page.get_pixmap(dpi=200, alpha=False)
                image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            else:
                image = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
                width, height = image.size
            total_pixels += image.width * image.height
            if total_pixels > policy["total_pixels"]:
                raise Rejected("RESOURCE_LIMIT")
            lines, quality = ocr(image, policy, directory, number)
            if document:
                lines = [
                    (
                        t,
                        [
                            b[0] * width / image.width,
                            b[1] * height / image.height,
                            b[2] * width / image.width,
                            b[3] * height / image.height,
                        ],
                        c,
                    )
                    for t, b, c in lines
                ]
            method = "TESSERACT"
            if "tesseract" not in libraries:
                engine = subprocess.run(
                    [policy["tesseract"], "--version"], capture_output=True, timeout=5, check=False
                )
                libraries["tesseract"] = (engine.stdout.decode(errors="replace").splitlines() or ["unknown"])[
                    0
                ][:100]
                for language in policy["language"].split("+"):
                    if re.fullmatch(r"[a-z_]{2,30}", language):
                        model = (
                            Path(policy["tesseract"]).resolve().parent
                            / "tessdata"
                            / (language + ".traineddata")
                        )
                        libraries[language + "_model_sha256"] = (
                            hashlib.sha256(model.read_bytes()).hexdigest()
                            if model.is_file() and model.stat().st_size <= 50 * 1024**2
                            else "UNAVAILABLE"
                        )
        texts.extend(t for t, _, _ in lines)
        fields += fields_from_lines(lines, number, method)
        pages.append({"page": number, "width": width, "height": height, "method": method, **quality})
    text = "\n".join(texts).casefold()
    detected = [key for key, label in TYPES.items() if label in text]
    quality = (
        "UNREADABLE"
        if any(p["quality"] == "UNREADABLE" for p in pages)
        else ("MARGINAL" if any(p["quality"] == "MARGINAL" for p in pages) else "READABLE")
    )
    return {
        "pages": pages,
        "fields": fields,
        "detected_types": detected,
        "quality": quality,
        "libraries": libraries,
        "language": policy["language"],
        "unknown_fields": sorted(set(LABELS.values()) - {f["field_key"] for f in fields}),
    }


def main():
    directory = Path(sys.argv[1])
    # Parent applies OS resource caps before opening the gate.
    deadline = time.monotonic() + 10
    while not (directory / "go").exists():
        if time.monotonic() > deadline:
            return
        time.sleep(0.02)
    if os.name != "nt":
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
        resource.setrlimit(resource.RLIMIT_CPU, (100, 100))
        resource.setrlimit(resource.RLIMIT_FSIZE, (25 * 1024**2, 25 * 1024**2))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    policy = json.loads((directory / "policy.json").read_text())
    try:
        result = {"ok": True, **parse(directory / "input", policy, directory)}
    except Rejected as exc:
        result = {"ok": False, "code": str(exc)}
    except Exception:
        result = {"ok": False, "code": "PROCESSING_FAILED"}
    (directory / "result.json").write_text(json.dumps(result), encoding="utf-8")


if __name__ == "__main__":
    main()
