"""Integration tests using real UE project config files.

Skipped if UE_PROJECT_PATH is not set.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("UE_PROJECT_PATH"),
    reason="UE_PROJECT_PATH not set",
)


class TestRealConfig:
    def test_list_config_files(self) -> None:
        from unreal_config_mcp.server import _reset_state, get_config_files
        _reset_state()
        result = get_config_files()
        assert "DefaultEngine" in result

    def test_get_section(self) -> None:
        from unreal_config_mcp.server import _reset_state, get_section
        _reset_state()
        result = get_section("DefaultEngine", "/Script/Engine.RendererSettings")
        assert "r." in result

    def test_search_config(self) -> None:
        from unreal_config_mcp.server import _reset_state, search_config
        _reset_state()
        result = search_config("AudioMixer")
        assert "UseAudioMixer" in result
