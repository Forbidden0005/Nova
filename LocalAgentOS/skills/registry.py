"""skills/registry.py — Load, execute, and prune auto-generated skills."""
from __future__ import annotations
import importlib.util
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from config import PRUNE_MIN_SUCCESS, PRUNE_MIN_USAGE, SKILLS_DIR, TOP_K_SKILLS

logger = logging.getLogger(__name__)


class SkillRegistry:
    """Manages lifecycle of auto-generated agent skills stored in ~/.agent_skills/"""

    def __init__(self, skills_dir: Path = SKILLS_DIR) -> None:
        self._skills_dir = skills_dir
        self._skills_dir.mkdir(parents=True, exist_ok=True)
        self._registry: dict[str, dict[str, Any]] = {}
        self.reload()

    def reload(self) -> int:
        self._registry.clear()
        for skill_file in sorted(self._skills_dir.glob("*_skill.py")):
            name = skill_file.stem.replace("_skill", "")
            meta_file = self._skills_dir / f"{name}_meta.json"
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text())
                except json.JSONDecodeError:
                    continue
            else:
                meta = self._default_meta(name)
                meta_file.write_text(json.dumps(meta, indent=2))
            module = self._load_module(name, skill_file)
            if module is None:
                continue
            run_fn = getattr(module, "run", None)
            if run_fn is None:
                continue
            self._registry[name] = {"module": module, "meta": meta, "callable": run_fn}
        logger.info("SkillRegistry: %d skills loaded", len(self._registry))
        return len(self._registry)

    def execute(self, skill_name: str, **kwargs: Any) -> Any:
        if skill_name not in self._registry:
            raise KeyError(f"Unknown skill: {skill_name}")
        entry = self._registry[skill_name]
        meta = entry["meta"]
        meta["usage_count"] = meta.get("usage_count", 0) + 1
        try:
            result = entry["callable"](**kwargs)
            meta["success_rate"] = 0.9 * meta.get("success_rate", 0.5) + 0.1
            return result
        except Exception as exc:
            meta["success_rate"] = 0.9 * meta.get("success_rate", 0.5)
            raise RuntimeError(f"Skill '{skill_name}' raised: {exc}") from exc
        finally:
            self._save_meta(skill_name, meta)

    def prune(self) -> list[str]:
        pruned = []
        for name in list(self._registry.keys()):
            meta = self._registry[name]["meta"]
            if meta.get("usage_count", 0) >= PRUNE_MIN_USAGE and meta.get("success_rate", 1.0) < PRUNE_MIN_SUCCESS:
                self._delete_skill(name)
                pruned.append(name)
        return pruned

    def all_metadata(self) -> dict[str, dict[str, Any]]:
        return {name: entry["meta"] for name, entry in self._registry.items()}

    def get_skill_names(self) -> list[str]:
        return list(self._registry.keys())

    def get_top_skills(self, n: int = TOP_K_SKILLS) -> list[str]:
        return sorted(
            self._registry.keys(),
            key=lambda nm: self._registry[nm]["meta"].get("success_rate", 0) * self._registry[nm]["meta"].get("usage_count", 0),
            reverse=True,
        )[:n]

    def _load_module(self, name: str, skill_file: Path):
        module_name = f"_skill_{name}"
        spec = importlib.util.spec_from_file_location(module_name, str(skill_file))
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
            return module
        except Exception as exc:
            logger.error("Error loading skill '%s': %s", name, exc)
            return None

    def _save_meta(self, name: str, meta: dict[str, Any]) -> None:
        try:
            (self._skills_dir / f"{name}_meta.json").write_text(json.dumps(meta, indent=2))
        except OSError:
            pass

    def _delete_skill(self, name: str) -> None:
        for suffix in ["_skill.py", "_meta.json"]:
            fp = self._skills_dir / f"{name}{suffix}"
            if fp.exists():
                fp.unlink()
        self._registry.pop(name, None)
        sys.modules.pop(f"_skill_{name}", None)

    @staticmethod
    def _default_meta(name: str) -> dict[str, Any]:
        return {
            "name": name, "description": f"Auto-generated skill: {name}",
            "created_at": datetime.utcnow().isoformat(),
            "usage_count": 0, "success_rate": 0.5,
            "keywords": name.replace("_", " ").split(),
        }
