import os
import pathlib
import sys

os.environ.setdefault("JWT_SECRET", "test-secret")
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "advisor")]
