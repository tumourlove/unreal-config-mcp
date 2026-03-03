"""MCP server with 6 tools for UE Config/INI intelligence."""

from __future__ import annotations

import sqlite3

from mcp.server.fastmcp import FastMCP

from unreal_config_mcp.config import (
    UE_ENGINE_PATH,
    UE_PROJECT_PATH,
    UE_SOURCE_DB_PATH,
)
from unreal_config_mcp.config_manager import ConfigManager
from unreal_config_mcp.editor_bridge import EditorBridge, EditorNotRunning

mcp = FastMCP(
    "unreal-config",
    instructions=(
        "Config/INI intelligence for Unreal Engine. "
        "Resolve config inheritance chains, search INI files, "
        "diff project vs engine defaults, and explain CVars."
    ),
)

_bridge: EditorBridge | None = None
_manager: ConfigManager | None = None
_source_db_path: str = UE_SOURCE_DB_PATH


def _reset_state() -> None:
    """Reset all singletons (for testing)."""
    global _bridge, _manager, _source_db_path
    if _bridge:
        _bridge.disconnect()
    _bridge = None
    _manager = None
    _source_db_path = ""


def _get_bridge() -> EditorBridge:
    """Lazy-init the editor bridge."""
    global _bridge
    if _bridge is not None:
        return _bridge
    _bridge = EditorBridge(auto_connect=False)
    return _bridge


def _get_manager() -> ConfigManager:
    """Lazy-init the config manager."""
    global _manager
    if _manager is not None:
        return _manager
    _manager = ConfigManager(
        project_path=UE_PROJECT_PATH,
        engine_path=UE_ENGINE_PATH or None,
    )
    return _manager


@mcp.tool()
def get_config_files() -> str:
    """List all INI config files in the project and engine with their roles.

    Shows file names, roles (engine default, project override, local saved),
    sizes, and last-modified times.
    """
    mgr = _get_manager()
    files = mgr.list_config_files()
    if not files:
        return "No config files found."

    lines = ["Config files:", ""]
    current_role = ""
    for f in files:
        if f["role"] != current_role:
            current_role = f["role"]
            lines.append(f"  [{current_role}]")
        size_kb = f["size"] / 1024
        lines.append(f"    {f['name']}.ini ({size_kb:.1f} KB)")

    return "\n".join(lines)


@mcp.tool()
def get_section(file: str, section: str = "") -> str:
    """Get all key-value pairs in a section of a config file.

    file: Short name like 'DefaultEngine' or 'BaseEngine'
    section: Section name like '/Script/Engine.RendererSettings'. If empty, lists all sections.
    """
    mgr = _get_manager()
    try:
        if not section:
            sections = mgr.list_sections(file)
            if not sections:
                return f"No sections found in {file}.ini"
            lines = [f"Sections in {file}.ini:", ""]
            for s in sections:
                lines.append(f"  [{s}]")
            return "\n".join(lines)

        entries = mgr.get_section(file, section)
        if not entries:
            return f"Section '{section}' not found or empty in {file}.ini"

        lines = [f"[{section}] in {file}.ini:", ""]
        for e in entries:
            op_prefix = {"set": "", "append": "+", "remove": "-", "clear": "!", "add_unique": "."}
            prefix = op_prefix.get(e["operation"], "")
            if e["operation"] == "clear":
                lines.append(f"  {prefix}{e['key']}")
            else:
                lines.append(f"  {prefix}{e['key']}={e['value']}")
        return "\n".join(lines)
    except FileNotFoundError as exc:
        return f"Error: {exc}"


@mcp.tool()
def search_config(pattern: str) -> str:
    """Search across all INI files for keys or values matching a regex pattern.

    pattern: Regex pattern to search for (case-insensitive)
    """
    mgr = _get_manager()
    results = mgr.search_config(pattern)
    if not results:
        return f"No matches for '{pattern}'."

    lines = [f"Found {len(results)} matches for '{pattern}':", ""]
    for r in results:
        lines.append(f"  {r['file']}.ini [{r['section']}] line {r['line_number']}")
        lines.append(f"    {r['key']}={r['value']}")
    return "\n".join(lines)


@mcp.tool()
def resolve_setting(section: str, key: str) -> str:
    """Resolve the effective value of a config setting across the inheritance chain.

    section: INI section name, e.g. '/Script/Engine.RendererSettings'
    key: Setting key, e.g. 'r.AntiAliasingMethod'

    Shows which file set each value and the final effective result.
    Optionally queries the running editor for the runtime value.
    """
    mgr = _get_manager()
    result = mgr.resolve_setting(section, key)

    if not result["chain"]:
        return f"Setting '{key}' not found in section '{section}'."

    lines = [
        f"Setting: [{section}] {key}",
        f"Effective value: {result['effective_value']}",
        "",
        "Inheritance chain:",
    ]
    for i, entry in enumerate(result["chain"]):
        marker = " (effective)" if i == len(result["chain"]) - 1 and entry["operation"] == "set" else ""
        lines.append(
            f"  {i + 1}. {entry['file']} (line {entry['line_number']})"
        )
        lines.append(
            f"     [{entry['operation']}] {key}={entry['value']}{marker}"
        )

    # Try editor bridge for runtime confirmation
    try:
        bridge = _get_bridge()
        command = (
            "import unreal\n"
            f"val = unreal.SystemLibrary.get_console_variable_string_value('{key}')\n"
            "print(val)"
        )
        bridge_result = bridge.run_command(command, exec_mode="ExecuteFile")
        if bridge_result.get("success"):
            raw = bridge_result.get("output", "")
            if isinstance(raw, list):
                parts = []
                for item in raw:
                    if isinstance(item, dict):
                        parts.append(item.get("output", ""))
                    else:
                        parts.append(str(item))
                runtime_val = "\n".join(parts).strip()
            else:
                runtime_val = str(raw).strip()
            if runtime_val:
                lines.append("")
                lines.append(f"Runtime value (from editor): {runtime_val}")
    except EditorNotRunning:
        lines.append("")
        lines.append("(Editor not running — runtime value not available)")
    except Exception:
        pass

    return "\n".join(lines)


@mcp.tool()
def explain_setting(section: str, key: str) -> str:
    """Explain what a config setting or CVar does by looking up its registration in engine source.

    section: INI section name
    key: Setting key / CVar name, e.g. 'r.AntiAliasingMethod'

    Queries the unreal-source-mcp database for the CVar definition and description.
    """
    if not _source_db_path:
        return (
            "Source database not configured. "
            "Set UE_SOURCE_DB_PATH to the unreal-source-mcp SQLite database path."
        )

    try:
        conn = sqlite3.connect(_source_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT name, file, line, definition FROM symbols "
            "WHERE definition LIKE ? OR name LIKE ? LIMIT 10",
            (f"%{key}%", f"%{key}%"),
        )
        rows = cursor.fetchall()
        conn.close()
    except (sqlite3.Error, OSError) as exc:
        return f"Error reading source database: {exc}"

    if not rows:
        return f"No CVar registration found for '{key}' in engine source."

    lines = [f"CVar: {key}", ""]
    for row in rows:
        lines.append(f"  Symbol: {row['name']}")
        lines.append(f"  File: {row['file']}:{row['line']}")
        definition = row["definition"]
        if definition:
            lines.append(f"  Definition: {definition[:300]}")
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
def diff_from_default(file: str) -> str:
    """Compare a project Default*.ini against its engine Base*.ini counterpart.

    file: Short name like 'DefaultEngine'

    Shows what the project has added, changed, or removed vs engine defaults.
    """
    mgr = _get_manager()
    try:
        diff = mgr.diff_from_default(file)
    except FileNotFoundError as exc:
        return f"Error: {exc}"

    lines = [f"Diff: {file}.ini vs engine defaults", ""]

    if diff["changed"]:
        lines.append(f"Changed ({len(diff['changed'])}):")
        for c in diff["changed"]:
            lines.append(f"  [{c['section']}] {c['key']}")
            lines.append(f"    engine: {c['engine_value']}")
            lines.append(f"    project: {c['project_value']}")
        lines.append("")

    if diff["added"]:
        lines.append(f"Added ({len(diff['added'])}):")
        for a in diff["added"]:
            lines.append(f"  [{a['section']}] {a['key']}={a['value']}")
        lines.append("")

    if diff["removed"]:
        lines.append(f"Removed ({len(diff['removed'])}):")
        for r in diff["removed"]:
            lines.append(f"  [{r['section']}] {r['key']} (was: {r['engine_value']})")
        lines.append("")

    if not diff["changed"] and not diff["added"] and not diff["removed"]:
        lines.append("No differences — project matches engine defaults.")

    return "\n".join(lines)


def main() -> None:
    """Run the MCP server."""
    mcp.run()
