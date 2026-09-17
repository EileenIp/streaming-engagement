"""Download provenance: what each raw file is, where it came from, when, and its checksum.

Raw files are gitignored; the manifest is not. A loader that finds a file
whose checksum no longer matches its manifest entry stops, because a quietly
replaced raw file is how a result stops being reproducible.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from src.config import MANIFEST, ROOT


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _read(manifest: Path) -> dict:
    return json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}


def record(path: Path, source: str, url: str, manifest: Path = MANIFEST, **extra) -> dict:
    entries = _read(manifest)
    key = path.resolve().relative_to(ROOT).as_posix() if path.resolve().is_relative_to(ROOT) else str(path)
    entries[key] = {
        "source": source,
        "url": url,
        "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        **extra,
    }
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(dict(sorted(entries.items())), indent=2) + "\n", encoding="utf-8")
    return entries[key]


def verify(path: Path, manifest: Path = MANIFEST) -> dict:
    key = path.resolve().relative_to(ROOT).as_posix() if path.resolve().is_relative_to(ROOT) else str(path)
    entry = _read(manifest).get(key)
    if entry is None:
        raise FileNotFoundError(f"{key} is not in the manifest; download it through its ingest module")
    if sha256(path) != entry["sha256"]:
        raise ValueError(f"{key} no longer matches the checksum recorded on {entry['downloaded_at']}")
    return entry
