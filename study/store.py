"""Append-only JSONL files for one stage of the study (pilot or full)."""
import json
import threading
from pathlib import Path

FILES = ("answers", "codings", "errors")


class Store:
    def __init__(self, root: Path):
        self.dir = root
        self.dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def path(self, name):
        return self.dir / f"{name}.jsonl"

    def load(self, name):
        p = self.path(name)
        if not p.exists():
            return []
        return [json.loads(line) for line in p.open(encoding="utf-8") if line.strip()]

    def append(self, name, row):
        with self._lock, self.path(name).open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
