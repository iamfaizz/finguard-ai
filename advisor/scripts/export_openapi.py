"""Step 1.4: write the advisor's OpenAPI spec to docs/openapi/advisor.json.

Run from advisor/:  python -m scripts.export_openapi
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))  # so `shared` is importable outside Docker

from app.main import app  # noqa: E402

out = ROOT / "docs" / "openapi" / "advisor.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
print(f"wrote {out}")