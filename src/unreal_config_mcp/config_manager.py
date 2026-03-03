"""Config manager: INI inheritance chain resolution with mtime-based caching."""

from __future__ import annotations

import re
from pathlib import Path

from unreal_config_mcp.ini_parser import IniFile, IniParser


def _default_to_base_name(default_name: str) -> str | None:
    """Convert 'DefaultEngine' to 'BaseEngine', etc."""
    if default_name.startswith("Default"):
        return "Base" + default_name[7:]
    return None


def _default_to_saved_name(default_name: str) -> str | None:
    """Convert 'DefaultEngine' to 'Engine', etc."""
    if default_name.startswith("Default"):
        return default_name[7:]
    return None


class ConfigManager:
    """Manages UE config files with inheritance chain resolution and caching."""

    def __init__(
        self,
        project_path: Path | str,
        engine_path: Path | str | None = None,
    ) -> None:
        self._project_path = Path(project_path)
        self._engine_path = Path(engine_path) if engine_path else None
        self._parser = IniParser()
        self._cache: dict[Path, IniFile] = {}

    @property
    def _project_config_dir(self) -> Path:
        return self._project_path / "Config"

    @property
    def _engine_config_dir(self) -> Path | None:
        if self._engine_path is None:
            return None
        return self._engine_path / "Config"

    @property
    def _saved_config_dir(self) -> Path:
        return self._project_path / "Saved" / "Config" / "Windows"

    def _get_parsed(self, path: Path) -> IniFile:
        """Get a parsed INI file, using cache if mtime matches."""
        cached = self._cache.get(path)
        if cached is not None:
            try:
                current_mtime = path.stat().st_mtime
            except OSError:
                return cached
            if cached.mtime == current_mtime:
                return cached

        parsed = self._parser.parse(path)
        self._cache[path] = parsed
        return parsed

    def _resolve_file_path(self, short_name: str) -> Path:
        """Resolve a short name like 'DefaultEngine' or 'BaseEngine' to a full path."""
        project_path = self._project_config_dir / f"{short_name}.ini"
        if project_path.exists():
            return project_path

        if self._engine_config_dir:
            engine_path = self._engine_config_dir / f"{short_name}.ini"
            if engine_path.exists():
                return engine_path

        saved_path = self._saved_config_dir / f"{short_name}.ini"
        if saved_path.exists():
            return saved_path

        raise FileNotFoundError(
            f"Config file '{short_name}.ini' not found. "
            f"Available: {', '.join(self._list_short_names())}"
        )

    def _list_short_names(self) -> list[str]:
        """List all available config file short names."""
        names: list[str] = []
        for d in self._all_config_dirs():
            if d.exists():
                for f in sorted(d.glob("*.ini")):
                    names.append(f.stem)
        return names

    def _all_config_dirs(self) -> list[Path]:
        """Return all config directories in inheritance order."""
        dirs: list[Path] = []
        if self._engine_config_dir and self._engine_config_dir.exists():
            dirs.append(self._engine_config_dir)
        if self._project_config_dir.exists():
            dirs.append(self._project_config_dir)
        if self._saved_config_dir.exists():
            dirs.append(self._saved_config_dir)
        return dirs

    def _get_inheritance_chain(self, default_name: str) -> list[Path]:
        """Get the ordered list of INI files for a given Default*.ini name.

        Returns paths in inheritance order: Base*.ini -> Default*.ini -> Saved/*.ini
        """
        chain: list[Path] = []

        base_name = _default_to_base_name(default_name)
        if base_name and self._engine_config_dir:
            base_path = self._engine_config_dir / f"{base_name}.ini"
            if base_path.exists():
                chain.append(base_path)

        default_path = self._project_config_dir / f"{default_name}.ini"
        if default_path.exists():
            chain.append(default_path)

        saved_name = _default_to_saved_name(default_name)
        if saved_name:
            saved_path = self._saved_config_dir / f"{saved_name}.ini"
            if saved_path.exists():
                chain.append(saved_path)

        return chain

    def list_config_files(self) -> list[dict]:
        """List all INI files across engine, project, and saved dirs."""
        files: list[dict] = []
        role_map: dict[str, str] = {}
        if self._engine_config_dir:
            role_map[str(self._engine_config_dir)] = "Engine default"
        role_map[str(self._project_config_dir)] = "Project override"
        role_map[str(self._saved_config_dir)] = "Local saved"

        for d in self._all_config_dirs():
            role = role_map.get(str(d), "Unknown")
            for f in sorted(d.glob("*.ini")):
                stat = f.stat()
                files.append({
                    "name": f.stem,
                    "path": str(f),
                    "role": role,
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                })
        return files

    def list_sections(self, file_name: str) -> list[str]:
        """List all section names in an INI file."""
        path = self._resolve_file_path(file_name)
        parsed = self._get_parsed(path)
        return list(parsed.sections.keys())

    def get_section(self, file_name: str, section: str) -> list[dict]:
        """Get all entries in a section of a specific INI file."""
        path = self._resolve_file_path(file_name)
        parsed = self._get_parsed(path)
        sec = parsed.sections.get(section)
        if sec is None:
            return []
        return [
            {
                "key": e.key,
                "value": e.value,
                "operation": e.operation,
                "line_number": e.line_number,
            }
            for e in sec.entries
        ]

    def resolve_setting(self, section: str, key: str) -> dict:
        """Resolve a setting across the inheritance chain."""
        chain: list[dict] = []
        effective_value = None

        if self._project_config_dir.exists():
            for ini_path in sorted(self._project_config_dir.glob("Default*.ini")):
                default_name = ini_path.stem
                for file_path in self._get_inheritance_chain(default_name):
                    parsed = self._get_parsed(file_path)
                    sec = parsed.sections.get(section)
                    if sec is None:
                        continue
                    for entry in sec.entries:
                        if entry.key == key:
                            chain.append({
                                "file": str(file_path),
                                "value": entry.value,
                                "operation": entry.operation,
                                "line_number": entry.line_number,
                            })
                            if entry.operation == "set":
                                effective_value = entry.value
                            elif entry.operation == "clear":
                                effective_value = None

        return {
            "section": section,
            "key": key,
            "effective_value": effective_value,
            "chain": chain,
        }

    def search_config(self, pattern: str) -> list[dict]:
        """Regex search across all INI files for keys or values matching pattern."""
        regex = re.compile(pattern, re.IGNORECASE)
        results: list[dict] = []

        for d in self._all_config_dirs():
            if not d.exists():
                continue
            for ini_path in sorted(d.glob("*.ini")):
                parsed = self._get_parsed(ini_path)
                for sec_name, sec in parsed.sections.items():
                    for entry in sec.entries:
                        if regex.search(entry.key) or regex.search(entry.value):
                            results.append({
                                "file": ini_path.stem,
                                "path": str(ini_path),
                                "section": sec_name,
                                "key": entry.key,
                                "value": entry.value,
                                "line_number": entry.line_number,
                            })

        return results

    def diff_from_default(self, default_name: str) -> dict:
        """Compare a project Default*.ini against its engine Base*.ini counterpart."""
        base_name = _default_to_base_name(default_name)
        default_path = self._project_config_dir / f"{default_name}.ini"

        if not default_path.exists():
            raise FileNotFoundError(f"{default_name}.ini not found in project config")

        project_parsed = self._get_parsed(default_path)

        base_parsed: IniFile | None = None
        if base_name and self._engine_config_dir:
            base_path = self._engine_config_dir / f"{base_name}.ini"
            if base_path.exists():
                base_parsed = self._get_parsed(base_path)

        added: list[dict] = []
        changed: list[dict] = []
        removed: list[dict] = []

        if base_parsed is None:
            for sec_name, sec in project_parsed.sections.items():
                for entry in sec.entries:
                    if entry.operation == "set":
                        added.append({
                            "section": sec_name,
                            "key": entry.key,
                            "value": entry.value,
                        })
            return {"added": added, "changed": changed, "removed": removed}

        base_values: dict[tuple[str, str], str] = {}
        for sec_name, sec in base_parsed.sections.items():
            for entry in sec.entries:
                if entry.operation == "set":
                    base_values[(sec_name, entry.key)] = entry.value

        for sec_name, sec in project_parsed.sections.items():
            for entry in sec.entries:
                if entry.operation != "set":
                    continue
                base_key = (sec_name, entry.key)
                if base_key in base_values:
                    if base_values[base_key] != entry.value:
                        changed.append({
                            "section": sec_name,
                            "key": entry.key,
                            "engine_value": base_values[base_key],
                            "project_value": entry.value,
                        })
                else:
                    added.append({
                        "section": sec_name,
                        "key": entry.key,
                        "value": entry.value,
                    })

        project_values: set[tuple[str, str]] = set()
        for sec_name, sec in project_parsed.sections.items():
            for entry in sec.entries:
                if entry.operation == "set":
                    project_values.add((sec_name, entry.key))

        for (sec_name, key), value in base_values.items():
            if (sec_name, key) not in project_values:
                removed.append({
                    "section": sec_name,
                    "key": key,
                    "engine_value": value,
                })

        return {"added": added, "changed": changed, "removed": removed}
