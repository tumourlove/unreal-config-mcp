"""Tests for MCP server tools."""

from __future__ import annotations

import json
import sqlite3
import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def _make_config_dirs(tmp_path: Path) -> dict[str, Path]:
    """Create engine + project config for testing."""
    engine = tmp_path / "Engine"
    engine_config = engine / "Config"
    engine_config.mkdir(parents=True)
    project = tmp_path / "Project"
    project_config = project / "Config"
    project_config.mkdir(parents=True)
    saved = project / "Saved" / "Config" / "Windows"
    saved.mkdir(parents=True)

    (engine_config / "BaseEngine.ini").write_text(textwrap.dedent("""\
        [/Script/Engine.RendererSettings]
        r.AntiAliasingMethod=2
        r.DefaultFeature.MotionBlur=True

        [Audio]
        UseAudioMixer=False
    """))

    (project_config / "DefaultEngine.ini").write_text(textwrap.dedent("""\
        [/Script/Engine.RendererSettings]
        r.AntiAliasingMethod=4
        r.DefaultFeature.MotionBlur=False

        [Audio]
        UseAudioMixer=True
    """))

    (project_config / "DefaultGame.ini").write_text(textwrap.dedent("""\
        [/Script/EngineSettings.GeneralProjectSettings]
        ProjectID=ABC123
    """))

    return {"engine": engine, "project": project}


@pytest.fixture(autouse=True)
def reset_server():
    """Reset server state between tests."""
    from unreal_config_mcp.server import _reset_state
    _reset_state()
    yield
    _reset_state()


@pytest.fixture
def setup_server(tmp_path: Path):
    """Set up server with test config dirs."""
    dirs = _make_config_dirs(tmp_path)
    from unreal_config_mcp import server
    from unreal_config_mcp.config_manager import ConfigManager

    server._manager = ConfigManager(
        project_path=dirs["project"],
        engine_path=dirs["engine"],
    )
    return dirs


class TestGetConfigFiles:
    def test_lists_files(self, setup_server) -> None:
        from unreal_config_mcp.server import get_config_files
        result = get_config_files()
        assert "BaseEngine" in result
        assert "DefaultEngine" in result
        assert "DefaultGame" in result

    def test_shows_roles(self, setup_server) -> None:
        from unreal_config_mcp.server import get_config_files
        result = get_config_files()
        assert "Engine default" in result
        assert "Project override" in result


class TestGetSection:
    def test_returns_entries(self, setup_server) -> None:
        from unreal_config_mcp.server import get_section
        result = get_section("DefaultEngine", "/Script/Engine.RendererSettings")
        assert "r.AntiAliasingMethod" in result
        assert "4" in result

    def test_lists_sections_when_no_section(self, setup_server) -> None:
        from unreal_config_mcp.server import get_section
        result = get_section("DefaultEngine")
        assert "/Script/Engine.RendererSettings" in result
        assert "Audio" in result

    def test_unknown_file(self, setup_server) -> None:
        from unreal_config_mcp.server import get_section
        result = get_section("NonExistent", "Section")
        assert "not found" in result.lower() or "error" in result.lower()


class TestSearchConfig:
    def test_finds_matches(self, setup_server) -> None:
        from unreal_config_mcp.server import search_config
        result = search_config("AntiAliasing")
        assert "r.AntiAliasingMethod" in result

    def test_no_matches(self, setup_server) -> None:
        from unreal_config_mcp.server import search_config
        result = search_config("zzz_nonexistent_zzz")
        assert "no matches" in result.lower() or "0" in result


class TestResolveSetting:
    def test_shows_chain(self, setup_server) -> None:
        from unreal_config_mcp.server import resolve_setting
        result = resolve_setting("/Script/Engine.RendererSettings", "r.AntiAliasingMethod")
        assert "4" in result  # project value
        assert "2" in result  # engine value

    def test_not_found(self, setup_server) -> None:
        from unreal_config_mcp.server import resolve_setting
        result = resolve_setting("FakeSection", "FakeKey")
        assert "not found" in result.lower()


class TestDiffFromDefault:
    def test_shows_changes(self, setup_server) -> None:
        from unreal_config_mcp.server import diff_from_default
        result = diff_from_default("DefaultEngine")
        assert "r.AntiAliasingMethod" in result
        assert "changed" in result.lower() or "Changed" in result

    def test_no_engine_counterpart(self, setup_server) -> None:
        from unreal_config_mcp.server import diff_from_default
        result = diff_from_default("DefaultGame")
        assert "ProjectID" in result


class TestExplainSetting:
    def test_explain_with_db(self, setup_server, tmp_path: Path) -> None:
        """Test explain_setting with a mock unreal-source DB."""
        db_path = tmp_path / "source.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS symbols (
                id INTEGER PRIMARY KEY,
                name TEXT,
                kind TEXT,
                file TEXT,
                line INTEGER,
                definition TEXT
            )
        """)
        conn.execute("""
            INSERT INTO symbols (name, kind, file, line, definition)
            VALUES ('r.AntiAliasingMethod', 'variable', 'Engine/Source/Runtime/Renderer/Private/PostProcess/PostProcessAA.cpp', 42, 'static TAutoConsoleVariable<int32> CVarAntiAliasingMethod(TEXT("r.AntiAliasingMethod"), 2, TEXT("0:off, 2:TAA, 4:TSR"), ECVF_Scalability);')
        """)
        conn.commit()
        conn.close()

        from unreal_config_mcp import server
        server._source_db_path = str(db_path)

        result = server.explain_setting("/Script/Engine.RendererSettings", "r.AntiAliasingMethod")
        assert "AntiAliasingMethod" in result

    def test_explain_no_db(self, setup_server) -> None:
        from unreal_config_mcp import server
        server._source_db_path = ""
        result = server.explain_setting("Section", "r.SomeCVar")
        assert "not available" in result.lower() or "not configured" in result.lower()
