"""Pytest config — sets PYTHONPATH-friendly sys.path tweaks + asyncio mode."""
import sys
from pathlib import Path

# Ensure src/ is importable when running from apps/api-gateway
SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))