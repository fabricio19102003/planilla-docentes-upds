from __future__ import annotations

import ast
from pathlib import Path


CONSUMER_PATHS = (
    "app/routers/billing_publication.py",
    "app/routers/docente_portal.py",
    "app/services/billing_pdf_service.py",
    "app/services/email_service.py",
    "app/services/billing_notification_preview.py",
    "app/services/billing_notification_service.py",
    "app/services/whatsapp_service.py",
    "app/workers/billing_notification_worker.py",
)


def test_published_billing_consumers_cannot_import_live_designation_model():
    backend_root = Path(__file__).resolve().parents[1]
    violations: list[str] = []

    for relative_path in CONSUMER_PATHS:
        path = backend_root / relative_path
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "app.models.designation":
                violations.append(relative_path)
            if isinstance(node, ast.Import) and any(
                alias.name == "app.models.designation" for alias in node.names
            ):
                violations.append(relative_path)

    assert violations == [], (
        "Published billing consumers must read immutable calculation/billing snapshots, "
        f"not the live Designation model: {sorted(set(violations))}"
    )
