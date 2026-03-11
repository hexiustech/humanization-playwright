"""Script registry: JSON index mapping patterns/domains to cached script files."""

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List


class ScriptRegistry:
    """Manages the JSON registry mapping patterns and domains to script files.

    Scripts are stored in a configurable directory as .py files.
    A registry.json index tracks metadata (domains tested, success/fail counts).
    """

    def __init__(self, scripts_dir: Path):
        self.scripts_dir = scripts_dir
        self.registry_file = scripts_dir / "registry.json"
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        self.scripts_dir.mkdir(parents=True, exist_ok=True)

    def find_pattern_script(self, pattern: str) -> Optional[str]:
        """Return the script filename if a pattern script exists, else None."""
        data = self._load()
        entry = data.get("patterns", {}).get(pattern)
        if entry and (self.scripts_dir / entry["script_file"]).exists():
            return entry["script_file"]
        return None

    def find_domain_script(self, domain: str) -> Optional[str]:
        """Return the script filename if a domain script exists, else None."""
        data = self._load()
        entry = data.get("domains", {}).get(domain)
        if entry and (self.scripts_dir / entry["script_file"]).exists():
            return entry["script_file"]
        return None

    def save_script(
        self,
        code: str,
        pattern: str,
        domain: str,
        is_domain_specific: bool = False,
    ) -> str:
        """Write script code to a file and register it. Returns filename."""
        if is_domain_specific:
            sanitized = self._sanitize_domain(domain)
            filename = f"domain_{sanitized}.py"
        else:
            filename = f"pattern_{pattern}.py"

        filepath = self.scripts_dir / filename
        filepath.write_text(code, encoding="utf-8")

        data = self._load()

        if is_domain_specific:
            if "domains" not in data:
                data["domains"] = {}
            if domain not in data["domains"]:
                data["domains"][domain] = {
                    "script_file": filename,
                    "patterns_handled": [],
                }
            data["domains"][domain]["script_file"] = filename
            if pattern not in data["domains"][domain]["patterns_handled"]:
                data["domains"][domain]["patterns_handled"].append(pattern)
        else:
            if "patterns" not in data:
                data["patterns"] = {}
            if pattern not in data["patterns"]:
                data["patterns"][pattern] = {
                    "script_file": filename,
                    "domains_tested": [],
                    "success_count": 0,
                    "fail_count": 0,
                }
            data["patterns"][pattern]["script_file"] = filename
            if domain not in data["patterns"][pattern]["domains_tested"]:
                data["patterns"][pattern]["domains_tested"].append(domain)

        self._save(data)
        return filename

    def load_script(self, script_file: str) -> str:
        """Read and return the script source code from disk."""
        filepath = self.scripts_dir / script_file
        return filepath.read_text(encoding="utf-8")

    def record_success(self, pattern: str, domain: str) -> None:
        """Increment success_count and add domain to domains_tested."""
        data = self._load()
        entry = data.get("patterns", {}).get(pattern)
        if entry:
            entry["success_count"] = entry.get("success_count", 0) + 1
            if domain not in entry.get("domains_tested", []):
                entry.setdefault("domains_tested", []).append(domain)
            self._save(data)

    def record_failure(self, pattern: str, domain: str) -> None:
        """Increment fail_count for a pattern."""
        data = self._load()
        entry = data.get("patterns", {}).get(pattern)
        if entry:
            entry["fail_count"] = entry.get("fail_count", 0) + 1
            self._save(data)

    def _load(self) -> Dict[str, Any]:
        if not self.registry_file.exists():
            return {}
        try:
            with open(self.registry_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save(self, data: Dict[str, Any]) -> None:
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self.scripts_dir), suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, str(self.registry_file))
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    @staticmethod
    def _sanitize_domain(domain: str) -> str:
        """Replace non-alphanumeric chars with underscores."""
        return re.sub(r"[^a-zA-Z0-9]", "_", domain)
