"""Create a local-only .env without printing or checking in its random password."""

import secrets
from pathlib import Path

root = Path(__file__).resolve().parent.parent
destination = root / ".env"
if destination.exists():
    print("Existing .env preserved. Configure it locally as needed.")
else:
    content = (root / ".env.example").read_text(encoding="utf-8")
    content = content.replace("DEMO_PASSWORD=\n", "DEMO_PASSWORD=" + secrets.token_urlsafe(24) + "\n")
    destination.write_text(content, encoding="utf-8")
    print("Created local .env with a random demo password. Read it locally to sign in; do not share it.")
