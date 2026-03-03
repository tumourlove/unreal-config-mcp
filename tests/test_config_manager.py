"""Tests for config manager (inheritance chain + caching)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from unreal_config_mcp.config_manager import ConfigManager


@pytest.fixture
def config_dirs(tmp_path: Path) -> dict[str, Path]:
    """Create engine and project config directories with sample INI files."""
    engine_dir = tmp_path / "Engine" / "Config"
    engine_dir.mkdir(parents=True)
    project_dir = tmp_path / "Project" / "Config"
    project_dir.mkdir(parents=True)
    saved_dir = tmp_path / "Project" / "Saved" / "Config" / "Windows"
    saved_dir.mkdir(parents=True)

    # Engine defaults
    (engine_dir / "BaseEngine.ini").write_text(textwrap.dedent("""\
        [/Script/Engine.RendererSettings]
        r.AntiAliasingMethod=2
        r.DefaultFeature.MotionBlur=True
        r.Nanite.ProjectEnabled=True

        [Audio]
        UseAudioMixer=False
    """))

    # Project overrides
    (project_dir / "DefaultEngine.ini").write_text(textwrap.dedent("""\
        [/Script/Engine.RendererSettings]
        r.AntiAliasingMethod=4
        r.DefaultFeature.MotionBlur=False

        [Audio]
        UseAudioMixer=True
    """))

    # Saved overrides (local user prefs)
    (saved_dir / "Engine.ini").write_text(textwrap.dedent("""\
        [/Script/Engine.RendererSettings]
        r.AntiAliasingMethod=0
    """))

    # A project-only file with no engine counterpart
    (project_dir / "DefaultGame.ini").write_text(textwrap.dedent("""\
        [/Script/EngineSettings.GeneralProjectSettings]
        ProjectID=ABC123
    """))

    return {
        "engine": tmp_path / "Engine",
        "project": tmp_path / "Project",
    }


@pytest.fixture
def manager(config_dirs: dict[str, Path]) -> ConfigManager:
    return ConfigManager(
        project_path=config_dirs["project"],
        engine_path=config_dirs["engine"],
    )


class TestConfigManager:
    def test_list_config_files(self, manager: ConfigManager) -> None:
        files = manager.list_config_files()
        names = [f["name"] for f in files]
        assert "BaseEngine" in names
        assert "DefaultEngine" in names
        assert "DefaultGame" in names

    def test_resolve_setting_project_overrides_engine(self, manager: ConfigManager) -> None:
        result = manager.resolve_setting("/Script/Engine.RendererSettings", "r.AntiAliasingMethod")
        # Saved overrides project overrides engine: 2 -> 4 -> 0
        assert result["effective_value"] == "0"
        assert len(result["chain"]) == 3

    def test_resolve_setting_chain_order(self, manager: ConfigManager) -> None:
        result = manager.resolve_setting("/Script/Engine.RendererSettings", "r.DefaultFeature.MotionBlur")
        # Engine=True, Project=False, no Saved override
        assert result["effective_value"] == "False"
        assert len(result["chain"]) == 2
        assert result["chain"][0]["value"] == "True"   # engine
        assert result["chain"][1]["value"] == "False"   # project

    def test_resolve_setting_not_found(self, manager: ConfigManager) -> None:
        result = manager.resolve_setting("/Script/Engine.RendererSettings", "r.NonExistent")
        assert result["effective_value"] is None
        assert len(result["chain"]) == 0

    def test_get_section(self, manager: ConfigManager) -> None:
        entries = manager.get_section("DefaultEngine", "/Script/Engine.RendererSettings")
        keys = [e["key"] for e in entries]
        assert "r.AntiAliasingMethod" in keys
        assert "r.DefaultFeature.MotionBlur" in keys

    def test_get_section_unknown_file(self, manager: ConfigManager) -> None:
        with pytest.raises(FileNotFoundError):
            manager.get_section("DefaultNonexistent", "SomeSection")

    def test_search_config(self, manager: ConfigManager) -> None:
        results = manager.search_config("AntiAliasing")
        assert len(results) >= 2  # engine + project (+ saved)
        files = {r["file"] for r in results}
        assert len(files) >= 2

    def test_search_config_no_match(self, manager: ConfigManager) -> None:
        results = manager.search_config("zzz_nonexistent_zzz")
        assert len(results) == 0

    def test_diff_from_default(self, manager: ConfigManager) -> None:
        diff = manager.diff_from_default("DefaultEngine")
        # r.AntiAliasingMethod changed from 2 to 4
        changed_keys = [c["key"] for c in diff["changed"]]
        assert "r.AntiAliasingMethod" in changed_keys
        assert "r.DefaultFeature.MotionBlur" in changed_keys

    def test_diff_from_default_no_engine(self, manager: ConfigManager) -> None:
        """DefaultGame has no BaseGame counterpart — everything is 'added'."""
        diff = manager.diff_from_default("DefaultGame")
        assert len(diff["added"]) > 0
        assert len(diff["changed"]) == 0

    def test_caching(self, manager: ConfigManager, config_dirs: dict[str, Path]) -> None:
        """Second call should use cache (same mtime)."""
        file_path = config_dirs["project"] / "Config" / "DefaultEngine.ini"
        result1 = manager._get_parsed(file_path)
        result2 = manager._get_parsed(file_path)
        assert result1 is result2  # Same object — cache hit

    def test_cache_invalidation(self, manager: ConfigManager, config_dirs: dict[str, Path]) -> None:
        """Touching the file should invalidate cache."""
        import time
        file_path = config_dirs["project"] / "Config" / "DefaultEngine.ini"
        result1 = manager._get_parsed(file_path)
        time.sleep(0.05)
        file_path.write_text(file_path.read_text() + "\n; touched\n")
        result2 = manager._get_parsed(file_path)
        assert result1 is not result2  # Different object — cache miss

    def test_no_engine_path(self, config_dirs: dict[str, Path]) -> None:
        """Manager works with no engine path — just project configs."""
        mgr = ConfigManager(project_path=config_dirs["project"], engine_path=None)
        files = mgr.list_config_files()
        names = [f["name"] for f in files]
        assert "DefaultEngine" in names
        assert "BaseEngine" not in names

    def test_list_sections(self, manager: ConfigManager) -> None:
        sections = manager.list_sections("DefaultEngine")
        assert "/Script/Engine.RendererSettings" in sections
        assert "Audio" in sections
