# CLAUDE.md — unreal-config-mcp

## Project Overview

**unreal-config-mcp** — Config/INI intelligence for Unreal Engine AI development.

An MCP (Model Context Protocol) server that provides structured access to UE config/INI files. Resolve config inheritance chains, search across all INI files, diff project overrides against engine defaults, and explain CVars by querying engine source — all without leaving the AI workflow.

**Complements** (does not replace):
- `unreal-source-mcp` — Engine-level source intelligence
- `unreal-project-mcp` — Project-level source intelligence
- `unreal-editor-mcp` — Build diagnostics and editor log tools
- `unreal-blueprint-mcp` — Blueprint graph reading

**We provide:** Config file intelligence — the settings layer between engine defaults and runtime behavior.

## Tech Stack

- **Language:** Python 3.11+
- **MCP SDK:** `mcp` Python package (FastMCP)
- **Distribution:** PyPI via `uvx unreal-config-mcp`
- **Package manager:** `uv` (for dev and build)
- **Optional:** SQLite (read-only, for `explain_setting` via unreal-source-mcp database)

## Project Structure

    unreal-config-mcp/
    ├── pyproject.toml
    ├── CLAUDE.md
    ├── README.md
    ├── src/
    │   └── unreal_config_mcp/
    │       ├── __init__.py          # Version
    │       ├── __main__.py          # CLI entry point
    │       ├── config.py            # Environment variables, path helpers
    │       ├── server.py            # FastMCP + 6 tool definitions
    │       ├── config_manager.py    # INI file discovery, parsing, resolution, diff
    │       ├── ini_parser.py        # Low-level UE INI parser (sections, ops, values)
    │       └── editor_bridge.py     # UE remote execution protocol client
    └── tests/
        ├── test_ini_parser.py       # INI parser unit tests
        ├── test_config_manager.py   # Config manager tests (temp file fixtures)
        └── test_server.py           # Server tool tests (mocked manager/bridge)

## Architecture

Three layers:

1. **ini_parser.py** — Parses individual UE INI files into structured data: sections, key-value pairs, and UE-specific operations (set, +append, -remove, .add_unique, !clear).
2. **config_manager.py** — Discovers INI files across engine/project/saved directories, manages the UE config inheritance chain (Base → Default → Saved), resolves effective values, diffs project vs engine defaults.
3. **server.py** — FastMCP server exposing 6 tools. Thin wrappers over ConfigManager that format results as human-readable strings.

Supporting modules:
- **editor_bridge.py** — UE remote execution protocol (UDP multicast discovery → TCP command channel). Used by `resolve_setting` to query runtime CVar values from the running editor.
- **SQLite (read-only)** — `explain_setting` queries the unreal-source-mcp database for CVar registration/definition in engine source.

## Build & Run

```bash
uv sync                                    # Install deps
uv run pytest tests/ -v                    # Run tests
uv run unreal-config-mcp                   # Run MCP server
uv run python -m unreal_config_mcp         # Alternative run
```

## MCP Configuration (for Claude Code)

```json
{
  "mcpServers": {
    "unreal-config": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/tumourlove/unreal-config-mcp.git", "unreal-config-mcp"],
      "env": {
        "UE_PROJECT_PATH": "D:/Unreal Projects/Leviathan"
      }
    }
  }
}
```

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `UE_PROJECT_PATH` | Path to UE project root (contains .uproject) — required |
| `UE_ENGINE_PATH` | Path to UE engine root — optional, enables engine Base*.ini access |
| `UE_SOURCE_DB_PATH` | Path to unreal-source-mcp SQLite database — optional, enables `explain_setting` |
| `UE_EDITOR_PYTHON_PORT` | TCP port for command connection (default: 6776) |
| `UE_MULTICAST_GROUP` | UDP multicast group for discovery (default: 239.0.0.1) |
| `UE_MULTICAST_PORT` | UDP multicast port (default: 6766) |
| `UE_MULTICAST_BIND` | Multicast bind address (default: 127.0.0.1) |

## MCP Tools (6)

| Tool | Purpose |
|------|---------|
| `get_config_files` | List all INI files in project and engine with roles and sizes |
| `get_section` | Get key-value pairs in a section, or list all sections in a file |
| `search_config` | Regex search across all INI files for keys or values |
| `resolve_setting` | Resolve effective value across inheritance chain (Base → Default → Saved) |
| `explain_setting` | Look up CVar registration and description from engine source database |
| `diff_from_default` | Compare project Default*.ini against engine Base*.ini counterpart |

## Coding Conventions

- **Lazy singletons** — `_get_bridge()` and `_get_manager()` init on first call, stored in module globals
- **`_reset_state()`** — every module with singletons exposes this for test teardown
- **Mock-based testing** — tests mock ConfigManager and EditorBridge; no real files or editor needed for server tests
- **Formatted string returns** — all tools return human-readable multi-line strings, not raw JSON
- Follow standard Python conventions: snake_case, type hints, docstrings on public functions
- Use `logging` module, not print statements
- Keep dependencies minimal — just `mcp>=1.0.0`
