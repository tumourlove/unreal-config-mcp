"""UE-aware INI file parser.

Handles UE-specific syntax:
  Key=Value     -> set
  +Key=Value    -> append (add to array)
  -Key=Value    -> remove (remove from array)
  .Key=Value    -> add_unique (add if not present)
  !Key          -> clear (remove key entirely)

Comments: lines starting with ; or //
Section headers: [SectionName] or [/Script/Module.ClassName]
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_SECTION_RE = re.compile(r"^\[(.+)\]\s*$")
_COMMENT_RE = re.compile(r"^\s*(;|//)")
_CLEAR_RE = re.compile(r"^!(\w[\w.]*)\s*$")
_ENTRY_RE = re.compile(r"^([+\-.]?)(\w[\w.]*)=(.*)")


@dataclass
class IniEntry:
    key: str
    value: str
    operation: str  # "set", "append", "remove", "clear", "add_unique"
    line_number: int


@dataclass
class IniSection:
    name: str
    entries: list[IniEntry] = field(default_factory=list)


@dataclass
class IniFile:
    path: Path
    sections: dict[str, IniSection] = field(default_factory=dict)
    mtime: float = 0.0


_OP_MAP = {
    "+": "append",
    "-": "remove",
    ".": "add_unique",
    "": "set",
}


class IniParser:
    """Parses a single UE INI file into structured data."""

    def parse(self, path: Path) -> IniFile:
        """Parse an INI file and return an IniFile."""
        text = path.read_text(encoding="utf-8-sig")
        ini_file = IniFile(path=path, mtime=path.stat().st_mtime)
        current_section: IniSection | None = None

        for line_number, raw_line in enumerate(text.splitlines(), start=1):
            line = raw_line.strip()

            if not line or _COMMENT_RE.match(line):
                continue

            section_match = _SECTION_RE.match(line)
            if section_match:
                name = section_match.group(1)
                if name not in ini_file.sections:
                    current_section = IniSection(name=name)
                    ini_file.sections[name] = current_section
                else:
                    current_section = ini_file.sections[name]
                continue

            clear_match = _CLEAR_RE.match(line)
            if clear_match and current_section is not None:
                current_section.entries.append(IniEntry(
                    key=clear_match.group(1),
                    value="",
                    operation="clear",
                    line_number=line_number,
                ))
                continue

            entry_match = _ENTRY_RE.match(line)
            if entry_match and current_section is not None:
                prefix = entry_match.group(1)
                key = entry_match.group(2)
                value = entry_match.group(3)
                current_section.entries.append(IniEntry(
                    key=key,
                    value=value,
                    operation=_OP_MAP.get(prefix, "set"),
                    line_number=line_number,
                ))
                continue

            if current_section is not None:
                logger.debug("Skipping unrecognized line %d: %s", line_number, raw_line)

        return ini_file
