"""Dumps the FastAPI app's OpenAPI schema to JSON without needing a live DB/Redis
connection - `create_engine()` in app/core/database.py is lazy, and the app's
`lifespan` (Redis pub/sub startup) only runs on actual ASGI startup, not on import.

Used by the frontend's `types:generate` script and by frontend-ci.yml to detect
schema drift between backend and frontend/types/generated.ts.

Usage: python backend/scripts/export_openapi.py [output_path]
(default output path: backend/openapi.json)
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402

output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "openapi.json"
output_path.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"wrote {output_path}")
