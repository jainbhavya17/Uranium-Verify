from uranium.config import Settings
from uranium.db import make_engine, session_factory
from uranium.models import PortalContent

with session_factory(make_engine(Settings().database_url))() as db:
    if not db.get(PortalContent, "public"):
        db.add(
            PortalContent(
                id="public",
                version=1,
                payload={
                    "announcement": {
                        "enabled": True,
                        "text": "A clearer application workspace is here",
                        "link": "/resources",
                    },
                    "notices": [
                        {
                            "id": "welcome-guide",
                            "title": "Your guide to a complete application",
                            "summary": "Prepare the right evidence for your category and academic year.",
                            "body": "Choose an application category and academic year to generate a tailored checklist. Upload original documents and resolve missing information before submitting.\n\nThis development prototype uses synthetic records and demonstration rule interpretations.",
                            "category": "Guidance",
                            "publishedOn": "2026-11-01",
                            "pinned": True,
                            "status": "Published",
                            "link": "/resources",
                        },
                        {
                            "id": "review-evidence",
                            "title": "Every finding, connected to its evidence",
                            "summary": "Review source pages, document versions and the reason for each finding.",
                            "body": "Authorized officers can open evidence, record their rationale and request clarification. Uncertain checks require human review. Issuer demonstrations are labelled MOCK and do not provide external confirmation.",
                            "category": "Updates",
                            "publishedOn": "2026-11-01",
                            "pinned": False,
                            "status": "Published",
                            "link": "/help",
                        },
                    ],
                },
            )
        )
        db.commit()
print("Public notices initialized or preserved.")
