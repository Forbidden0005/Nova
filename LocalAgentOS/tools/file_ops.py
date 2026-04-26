"""tools/file_ops.py — Directory scanning, duplicate detection, file I/O."""
from __future__ import annotations
import hashlib
import logging
import os
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
LARGE_FILE_BYTES: int = 100 * 1024 * 1024  # 100 MB


class FileOpsTool:

    def analyze_directory(self, path: str) -> dict[str, Any]:
        """Scan a directory tree and return stats, duplicates, large files."""
        root = Path(path)
        if not root.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        if not root.is_dir():
            raise NotADirectoryError(f"Not a directory: {path}")
        results: dict[str, Any] = {
            "total_files": 0, "total_size_mb": 0.0,
            "file_types": defaultdict(int), "duplicates": [], "large_files": [], "errors": [],
        }
        hash_map: dict[str, list[str]] = defaultdict(list)
        for dirpath, _, files in os.walk(root):
            for filename in files:
                fp = Path(dirpath) / filename
                try:
                    size = fp.stat().st_size
                except OSError as exc:
                    results["errors"].append(str(exc))
                    continue
                results["total_files"] += 1
                results["total_size_mb"] += size / (1024 * 1024)
                results["file_types"][fp.suffix.lower() or "(no ext)"] += 1
                if size >= LARGE_FILE_BYTES:
                    results["large_files"].append({"path": str(fp), "size_mb": round(size/1024/1024, 2)})
                if size <= 500 * 1024 * 1024:
                    h = self._sha256(fp)
                    if h:
                        hash_map[h].append(str(fp))
        for h, paths in hash_map.items():
            if len(paths) > 1:
                results["duplicates"].append({"hash": h, "count": len(paths), "paths": paths})
        results["total_size_mb"] = round(results["total_size_mb"], 2)
        results["file_types"] = dict(results["file_types"])
        logger.info("Scanned %s: %d files, %.1f MB, %d dupe groups",
                    path, results["total_files"], results["total_size_mb"], len(results["duplicates"]))
        return results

    def read_file(self, path: str, encoding: str = "utf-8") -> str:
        fp = Path(path)
        if not fp.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return fp.read_text(encoding=encoding, errors="replace")

    def write_file(self, path: str, content: str, encoding: str = "utf-8") -> None:
        fp = Path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding=encoding)
        logger.info("Wrote %d chars to %s", len(content), path)

    def move_file(self, src: str, dst: str, dry_run: bool = False) -> str:
        src_p, dst_p = Path(src), Path(dst)
        if not src_p.exists():
            raise FileNotFoundError(f"Source not found: {src}")
        if dry_run:
            logger.info("[DRY-RUN] Would move %s -> %s", src, dst)
            return str(dst_p)
        dst_p.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_p), str(dst_p))
        return str(dst_p)

    def delete_file(self, path: str, dry_run: bool = False) -> None:
        fp = Path(path)
        if not fp.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if dry_run:
            logger.info("[DRY-RUN] Would delete %s", path)
            return
        fp.unlink()

    def list_directory(self, path: str) -> list[dict[str, Any]]:
        root = Path(path)
        if not root.is_dir():
            raise NotADirectoryError(f"Not a directory: {path}")
        entries = []
        for entry in sorted(root.iterdir()):
            try:
                size = entry.stat().st_size if entry.is_file() else 0
                entries.append({"name": entry.name, "type": "dir" if entry.is_dir() else "file", "size_bytes": size})
            except OSError:
                pass
        return entries

    @staticmethod
    def _sha256(filepath: Path) -> str | None:
        h = hashlib.sha256()
        try:
            with filepath.open("rb") as fh:
                for chunk in iter(lambda: fh.read(65536), b""):
                    h.update(chunk)
            return h.hexdigest()
        except OSError:
            return None

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "name": "file_ops",
            "description": "Scan directories, find duplicates, read/write/move/delete files, list directory contents.",
            "keywords": ["file","folder","directory","scan","duplicate","disk","read","write","move","delete","size"],
        }
