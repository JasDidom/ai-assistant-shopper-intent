"""Load KEY=value pairs from the project's .env into os.environ (never overrides)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# STUDY_OUT lets a dry run write somewhere else, so mock data never mixes with real data.
OUT = Path(os.environ["STUDY_OUT"]) if os.environ.get("STUDY_OUT") else ROOT
DATA = OUT / "data"
RESULTS = OUT / "results"


def load_env():
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if v and k not in os.environ:
                os.environ[k] = v


def model_ids():
    return {
        "claude": os.environ.get("CLAUDE_MODEL", "claude-opus-5-5"),
        "gpt": os.environ.get("OPENAI_MODEL", "gpt-6.1-sol"),
        "gemini": os.environ.get("GEMINI_MODEL", "gemini-3.8-flash"),
    }
