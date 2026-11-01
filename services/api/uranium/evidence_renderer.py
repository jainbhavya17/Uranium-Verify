import base64
import json
import os
import sys
import time
from pathlib import Path


def render(root):
    import pymupdf
    from PIL import Image, ImageOps

    config = json.loads((root / "policy.json").read_text())
    options = config["options"]
    file = root / "input"
    number = options["page"]
    if options["media_type"] == "application/pdf":
        doc = pymupdf.open(file)
        if not 1 <= number <= len(doc):
            return {"ok": False, "code": "PAGE_UNAVAILABLE"}
        page = doc[number - 1]
        if page.rect.width * page.rect.height * (120 / 72) ** 2 > config["pixels"]:
            return {"ok": False, "code": "RESOURCE_LIMIT"}
        pix = page.get_pixmap(dpi=120, alpha=False)
        data = pix.tobytes("png")
        width, height = page.rect.width, page.rect.height
    else:
        if number != 1:
            return {"ok": False, "code": "PAGE_UNAVAILABLE"}
        import io

        image = ImageOps.exif_transpose(Image.open(file)).convert("RGB")
        width, height = image.size
        if width * height > config["pixels"]:
            return {"ok": False, "code": "RESOURCE_LIMIT"}
        image.thumbnail((1600, 2000))
        output = io.BytesIO()
        image.save(output, format="PNG")
        data = output.getvalue()
    return {
        "ok": True,
        "page": number,
        "width": width,
        "height": height,
        "png": base64.b64encode(data).decode(),
    }


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
        result = render(root)
    except Exception:
        result = {"ok": False, "code": "RENDER_UNAVAILABLE"}
    (root / "result.json").write_text(json.dumps(result), encoding="utf-8")
