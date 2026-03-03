"""Tests for UE-aware INI parser."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from unreal_config_mcp.ini_parser import IniEntry, IniFile, IniParser


@pytest.fixture
def parser() -> IniParser:
    return IniParser()


@pytest.fixture
def simple_ini(tmp_path: Path) -> Path:
    p = tmp_path / "Test.ini"
    p.write_text(textwrap.dedent("""\
        [Audio]
        UseAudioMixer=True

        [/Script/Engine.RendererSettings]
        r.GenerateMeshDistanceFields=True
        r.AntiAliasingMethod=4
    """))
    return p


@pytest.fixture
def array_ops_ini(tmp_path: Path) -> Path:
    p = tmp_path / "ArrayOps.ini"
    p.write_text(textwrap.dedent("""\
        [/Script/WindowsTargetPlatform.WindowsTargetSettings]
        -D3D12TargetedShaderFormats=PCD3D_SM5
        +D3D12TargetedShaderFormats=PCD3D_SM5
        +D3D12TargetedShaderFormats=PCD3D_SM6
    """))
    return p


@pytest.fixture
def comments_ini(tmp_path: Path) -> Path:
    p = tmp_path / "Comments.ini"
    p.write_text(textwrap.dedent("""\
        ; This is a comment
        [Section]
        // Another comment
        Key=Value
        ; Inline not standard but skip blank lines
    """))
    return p


@pytest.fixture
def clear_ini(tmp_path: Path) -> Path:
    p = tmp_path / "Clear.ini"
    p.write_text(textwrap.dedent("""\
        [Section]
        !OldKey
        .UniqueItem=Value1
    """))
    return p


@pytest.fixture
def empty_value_ini(tmp_path: Path) -> Path:
    p = tmp_path / "Empty.ini"
    p.write_text(textwrap.dedent("""\
        [Section]
        EmptyKey=
        NormalKey=Hello
    """))
    return p


class TestIniParser:
    def test_parse_simple_sections(self, parser: IniParser, simple_ini: Path) -> None:
        result = parser.parse(simple_ini)
        assert isinstance(result, IniFile)
        assert "Audio" in result.sections
        assert "/Script/Engine.RendererSettings" in result.sections

    def test_parse_simple_values(self, parser: IniParser, simple_ini: Path) -> None:
        result = parser.parse(simple_ini)
        audio = result.sections["Audio"]
        assert len(audio.entries) == 1
        assert audio.entries[0].key == "UseAudioMixer"
        assert audio.entries[0].value == "True"
        assert audio.entries[0].operation == "set"

    def test_parse_array_operations(self, parser: IniParser, array_ops_ini: Path) -> None:
        result = parser.parse(array_ops_ini)
        section = result.sections["/Script/WindowsTargetPlatform.WindowsTargetSettings"]
        assert len(section.entries) == 3
        assert section.entries[0].operation == "remove"
        assert section.entries[0].key == "D3D12TargetedShaderFormats"
        assert section.entries[0].value == "PCD3D_SM5"
        assert section.entries[1].operation == "append"
        assert section.entries[2].operation == "append"
        assert section.entries[2].value == "PCD3D_SM6"

    def test_parse_comments_skipped(self, parser: IniParser, comments_ini: Path) -> None:
        result = parser.parse(comments_ini)
        section = result.sections["Section"]
        assert len(section.entries) == 1
        assert section.entries[0].key == "Key"

    def test_parse_clear_and_add_unique(self, parser: IniParser, clear_ini: Path) -> None:
        result = parser.parse(clear_ini)
        section = result.sections["Section"]
        assert len(section.entries) == 2
        assert section.entries[0].operation == "clear"
        assert section.entries[0].key == "OldKey"
        assert section.entries[1].operation == "add_unique"
        assert section.entries[1].key == "UniqueItem"

    def test_parse_empty_value(self, parser: IniParser, empty_value_ini: Path) -> None:
        result = parser.parse(empty_value_ini)
        section = result.sections["Section"]
        assert section.entries[0].key == "EmptyKey"
        assert section.entries[0].value == ""
        assert section.entries[1].value == "Hello"

    def test_parse_stores_line_numbers(self, parser: IniParser, simple_ini: Path) -> None:
        result = parser.parse(simple_ini)
        audio = result.sections["Audio"]
        assert audio.entries[0].line_number == 2

    def test_parse_stores_mtime(self, parser: IniParser, simple_ini: Path) -> None:
        result = parser.parse(simple_ini)
        assert result.mtime == simple_ini.stat().st_mtime

    def test_parse_nonexistent_file(self, parser: IniParser, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            parser.parse(tmp_path / "nonexistent.ini")

    def test_parse_values_with_parens(self, parser: IniParser, tmp_path: Path) -> None:
        p = tmp_path / "Complex.ini"
        p.write_text(textwrap.dedent("""\
            [Section]
            CompressionOverrides=(bOverride=False,Threshold=5.0,Index=0)
        """))
        result = parser.parse(p)
        entry = result.sections["Section"].entries[0]
        assert entry.key == "CompressionOverrides"
        assert entry.value == "(bOverride=False,Threshold=5.0,Index=0)"

    def test_parse_duplicate_keys(self, parser: IniParser, tmp_path: Path) -> None:
        p = tmp_path / "Dupes.ini"
        p.write_text(textwrap.dedent("""\
            [Section]
            Key=First
            Key=Second
        """))
        result = parser.parse(p)
        entries = result.sections["Section"].entries
        assert len(entries) == 2
        assert entries[0].value == "First"
        assert entries[1].value == "Second"
