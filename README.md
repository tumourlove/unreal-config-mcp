# unreal-config-mcp

Config/INI intelligence for Unreal Engine AI development via [Model Context Protocol](https://modelcontextprotocol.io/).

Gives AI assistants structured access to UE config files — resolve config inheritance chains, search across all INI files, diff project overrides against engine defaults, and explain CVars by querying engine source.

## Why?

Unreal Engine's config system is a layered hierarchy of INI files (Base → Default → Saved) that controls everything from rendering settings to input bindings. AI assistants can read C++ and Blueprints, but they can't navigate this inheritance chain or understand why a setting has a particular runtime value. This server exposes the full config stack so AI agents can trace settings from engine defaults through project overrides to saved state.

**Complements** (does not replace):
- [unreal-source-mcp](https://github.com/tumourlove/unreal-source-mcp) — Engine-level source intelligence (full UE C++ and HLSL)
- [unreal-project-mcp](https://github.com/tumourlove/unreal-project-mcp) — Project-level source intelligence (your C++ code)
- [unreal-editor-mcp](https://github.com/tumourlove/unreal-editor-mcp) — Build diagnostics and editor log tools (Live Coding, error parsing, log search)
- [unreal-material-mcp](https://github.com/tumourlove/unreal-material-mcp) — Material graph intelligence, editing, and procedural creation (46 tools: expressions, parameters, instances, graph building, templates, C++ plugin)
- [unreal-blueprint-mcp](https://github.com/tumourlove/unreal-blueprint-mcp) — Blueprint graph reading (nodes, pins, connections, execution flow)
- [unreal-animation-mcp](https://github.com/tumourlove/unreal-animation-mcp) — Animation data inspector and editor (sequences, montages, blend spaces, ABPs, skeletons, 62 tools)
- [unreal-api-mcp](https://github.com/nicobailon/unreal-api-mcp) by [Nico Bailon](https://github.com/nicobailon) — API surface lookup (signatures, #include paths, deprecation warnings)

Together these servers give AI agents full-stack UE understanding: engine internals, API surface, your project code, config settings, build/runtime feedback, Blueprint graph data, animation data, and material graph intelligence + procedural creation.

## Quick Start

### Install from GitHub

```bash
uvx --from git+https://github.com/tumourlove/unreal-config-mcp.git unreal-config-mcp
```

### Claude Code Configuration

Add to your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "unreal-config": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/tumourlove/unreal-config-mcp.git", "unreal-config-mcp"],
      "env": {
        "UE_PROJECT_PATH": "D:/Unreal Projects/MyProject"
      }
    }
  }
}
```

Or run from local source during development:

```json
{
  "mcpServers": {
    "unreal-config": {
      "command": "uv",
      "args": ["run", "--directory", "C:/Projects/unreal-config-mcp", "unreal-config-mcp"],
      "env": {
        "UE_PROJECT_PATH": "D:/Unreal Projects/MyProject"
      }
    }
  }
}
```

## Tools

| Tool | Description |
|------|-------------|
| `get_config_files` | List all INI config files in the project and engine with their roles (engine default, project override, local saved), sizes, and last-modified times. |
| `get_section` | Get all key-value pairs in a section of a config file. Pass an empty section to list all sections in the file. |
| `search_config` | Regex search across all INI files for keys or values matching a pattern. Returns file, section, line number, and the matching key-value pair. |
| `resolve_setting` | Resolve the effective value of a config setting across the full inheritance chain (Base → Default → Saved). Shows which file set each value and the final result. Optionally queries the running editor for the runtime CVar value. |
| `explain_setting` | Explain what a config setting or CVar does by looking up its registration in engine source. Requires `UE_SOURCE_DB_PATH` pointing to the unreal-source-mcp SQLite database. |
| `diff_from_default` | Compare a project `Default*.ini` against its engine `Base*.ini` counterpart. Shows what the project has added, changed, or removed vs engine defaults. |

### Example Usage

**Resolve a rendering setting:**
> "Use `resolve_setting` with section `/Script/Engine.RendererSettings` and key `r.AntiAliasingMethod` to see the full inheritance chain."

**Search for a CVar across all config files:**
> "Use `search_config` with pattern `r\.Shadow` to find all shadow-related settings."

**Diff project overrides:**
> "Use `diff_from_default` with file `DefaultEngine` to see what your project changed from engine defaults."

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `UE_PROJECT_PATH` | Yes | Path to the UE project root (containing the .uproject file) |
| `UE_ENGINE_PATH` | No | Path to the UE engine root. Enables engine `Base*.ini` access for `resolve_setting` and `diff_from_default`. |
| `UE_SOURCE_DB_PATH` | No | Path to unreal-source-mcp SQLite database. Enables `explain_setting` tool. |
| `UE_EDITOR_PYTHON_PORT` | No | TCP port for editor Python bridge commands (default: `6776`) |
| `UE_MULTICAST_GROUP` | No | UDP multicast group for editor discovery (default: `239.0.0.1`) |
| `UE_MULTICAST_PORT` | No | UDP multicast port for editor discovery (default: `6766`) |
| `UE_MULTICAST_BIND` | No | Local interface to bind multicast listener (default: `127.0.0.1`) |

## How It Works

1. **INI Parser** — Parses UE INI files into structured data, handling UE-specific operations: `=` (set), `+` (append), `-` (remove), `.` (add unique), `!` (clear).

2. **Config Manager** — Discovers INI files across engine, project, and saved directories. Manages the UE config inheritance chain: engine `Base*.ini` → project `Default*.ini` → saved `*.ini`. Resolves effective values by replaying operations in order.

3. **Editor Bridge** — Optionally connects to a running UE editor via UDP multicast discovery and TCP command channel (same protocol as UE's `remote_execution.py`). Used by `resolve_setting` to confirm runtime CVar values.

4. **Source Database** — `explain_setting` queries the unreal-source-mcp SQLite database (read-only) for CVar registration, definition, and description from engine source.

## Adding to Your Project's CLAUDE.md

```markdown
## Config Intelligence (unreal-config MCP)

Use `unreal-config` MCP tools to inspect and understand UE config/INI settings.

| Tool | When |
|------|------|
| `get_config_files` | See what config files exist |
| `get_section` | Read specific sections or list sections in a file |
| `search_config` | Find settings by name or value across all INI files |
| `resolve_setting` | Trace a setting through the inheritance chain |
| `explain_setting` | Look up what a CVar does in engine source |
| `diff_from_default` | See project overrides vs engine defaults |
```

## Development

```bash
# Clone and install
git clone https://github.com/tumourlove/unreal-config-mcp.git
cd unreal-config-mcp
uv sync

# Run tests
uv run pytest tests/ -v

# Run server locally
uv run unreal-config-mcp
```

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Unreal Engine 5.x project (for config files to read)

## License

MIT
