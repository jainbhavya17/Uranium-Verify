"""Offline native verification. Runs only after safety validation, under worker resource caps."""

import json
import hashlib
import os
import sys
import time
from pathlib import Path


def inspect(path, options):
    result = {}
    from importlib.metadata import version

    try:
        import c2pa
        from importlib.metadata import version

        settings = {
            "verify": {"remote_manifest_fetch": False, "ocsp_fetch": False, "verify_cert_anchors": True}
        }
        if options.get("c2pa_anchors"):
            settings["trust"] = {"trust_anchors": options["c2pa_anchors"]}
        with c2pa.Context.from_dict(settings) as ctx:
            with open(path, "rb") as stream:
                with c2pa.Reader(options["media_type"], stream, context=ctx) as reader:
                    report = json.loads(reader.json())
                    active = report.get("active_manifest")
                    state = reader.get_validation_state()
                    result["c2pa"] = {
                        "outcome": (
                            "NO_SIGNAL"
                            if not active
                            else "TRUSTED"
                            if str(state).lower() == "trusted"
                            else "VALID_UNTRUSTED"
                            if str(state).lower() == "valid"
                            else "INVALID"
                        ),
                        "validation_state": str(state),
                        "active_manifest": active,
                        "method": "c2pa-python/" + version("c2pa-python"),
                        "issuer_authenticity_confirmed": False,
                        "remote_fetch": False,
                        "trust_anchor_sha256": hashlib.sha256(options["c2pa_anchors"].encode()).hexdigest()
                        if options.get("c2pa_anchors")
                        else None,
                    }
    except ImportError:
        result["c2pa"] = {"outcome": "UNAVAILABLE", "method": "c2pa-python"}
    except Exception as exc:
        # SDK distinguishes absence from validation/unsupported errors; no raw diagnostic payload leaks.
        kind = str(exc).casefold()
        result["c2pa"] = {
            "outcome": "NO_SIGNAL"
            if "manifest not found" in kind or "jumbf not found" in kind or "manifestnotfound" in kind
            else "UNAVAILABLE",
            "method": "c2pa-python",
            "issuer_authenticity_confirmed": False,
        }
    result["pdf_signature"] = {"outcome": "NOT_SUPPORTED", "method": "pyHanko-offline"}
    if options["media_type"] == "application/pdf":
        try:
            from pyhanko.pdf_utils.reader import PdfFileReader
            from pyhanko.sign.validation import validate_pdf_signature
            from pyhanko_certvalidator import ValidationContext
            from asn1crypto import pem, x509

            roots = []
            if options.get("pdf_anchors"):
                for _, _, der in pem.unarmor(options["pdf_anchors"].encode(), multiple=True):
                    roots.append(x509.Certificate.load(der))
            with open(path, "rb") as stream:
                reader = PdfFileReader(stream)
                signatures = []
                for sig in reader.embedded_signatures[:10]:
                    status = validate_pdf_signature(
                        sig,
                        signer_validation_context=ValidationContext(trust_roots=roots, allow_fetching=False),
                    )
                    signatures.append(
                        {
                            "intact": status.intact,
                            "cryptographically_valid": status.valid,
                            "chain_trusted": status.trusted,
                            "outcome": "TRUSTED"
                            if status.intact and status.valid and status.trusted
                            else "VALID_UNTRUSTED"
                            if status.intact and status.valid
                            else "INVALID",
                        }
                    )
                result["pdf_signature"] = {
                    "outcome": "NO_SIGNATURE" if not signatures else "CHECKED",
                    "signatures": signatures,
                    "method": "pyHanko-offline/" + version("pyhanko"),
                    "trust_anchor_sha256": hashlib.sha256(options["pdf_anchors"].encode()).hexdigest()
                    if options.get("pdf_anchors")
                    else None,
                    "revocation": "NOT_FETCHED",
                    "drawn_signature_is_not_proof": True,
                }
        except ImportError:
            result["pdf_signature"] = {
                "outcome": "UNAVAILABLE",
                "method": "pyHanko-offline",
                "reason": "DEPENDENCY_UNAVAILABLE",
            }
        except Exception as exc:
            result["pdf_signature"] = {
                "outcome": "UNAVAILABLE",
                "method": "pyHanko-offline",
                "reason": type(exc).__name__,
            }
    result["qr"] = {"outcome": "NO_SIGNAL", "method": "OpenCV QRCodeDetector; no URL is fetched"}
    try:
        import cv2
        import numpy as np
        from PIL import Image
        import pymupdf

        if options["media_type"] == "application/pdf":
            doc = pymupdf.open(path)
            pix = doc[0].get_pixmap(dpi=100, alpha=False)
            image = np.asarray(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
            metadata = doc.metadata
        else:
            image = np.asarray(Image.open(path).convert("RGB"))
            metadata = {}
        _, points, _ = cv2.QRCodeDetector().detectAndDecode(image)
        if points is not None:
            result["qr"]["outcome"] = "DETECTED_UNVERIFIED"
        result["metadata"] = {
            "outcome": "OBSERVED",
            "method": "PyMuPDF/Pillow",
            "indicators": ["Producer metadata is a user-controlled claim"]
            if metadata.get("producer")
            else [],
            "authenticity_confirmed": False,
        }
    except Exception:
        result["qr"]["outcome"] = "UNAVAILABLE"
    result["watermark"] = {
        "outcome": "UNAVAILABLE",
        "method": "provider-specific; no authorized detector configured",
        "authenticity_confirmed": False,
    }
    return {"ok": True, "checks": result}


if __name__ == "__main__":
    root = Path(sys.argv[1])
    deadline = time.monotonic() + 10
    while not (root / "go").exists():
        if time.monotonic() > deadline:
            sys.exit(1)
        time.sleep(0.02)
    if os.name != "nt":
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
        resource.setrlimit(resource.RLIMIT_CPU, (100, 100))
    try:
        result = inspect(root / "input", json.loads((root / "policy.json").read_text())["options"])
    except Exception:
        result = {"ok": False, "code": "PROVENANCE_UNAVAILABLE"}
    (root / "result.json").write_text(json.dumps(result), encoding="utf-8")
