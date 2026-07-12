from __future__ import annotations

import ast
import unittest
from pathlib import Path

import discord

from bot.commands.recording import CompatWaveSink


def _receive_pipeline_sources() -> list[Path]:
    base = Path(discord.__file__).parent
    files = list((base / "voice" / "receive").glob("*.py"))
    files.append(base / "opus.py")
    return [f for f in files if f.exists()]


def _sink_attribute_accesses(source: str) -> set[str]:
    """sink.X / self.sink.X 形式の属性アクセスを AST で列挙する。

    コメント・文字列リテラル内の擬似アクセスは AST 解析で自然に除外される。
    """
    accessed: set[str] = set()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        value = node.value
        is_bare = isinstance(value, ast.Name) and value.id == "sink"
        is_member = isinstance(value, ast.Attribute) and value.attr == "sink"
        if is_bare or is_member:
            accessed.add(node.attr)
    return accessed


class PycordSinkContractTest(unittest.TestCase):
    """py-cord の受信パイプラインが sink に要求する契約を、実物ソースの AST から抽出して検証する。

    モックでは「自分の思い込み」しか検証できず、ライブラリ内部との契約ずれ
    （例: 2.8.0 で突然要求された is_opus / __sink_listeners__）は捕まえられない。
    このテストは py-cord のバージョンが上がって契約が変わった瞬間に CI で落ちる。
    """

    def test_compat_sink_satisfies_receive_pipeline_contract(self) -> None:
        required: set[str] = set()
        for path in _receive_pipeline_sources():
            required |= _sink_attribute_accesses(path.read_text())

        self.assertTrue(required, "解析対象が空 — py-cord の構成が変わった可能性")

        sink = CompatWaveSink()
        missing = sorted(
            attr for attr in required if not attr.startswith("__") and not hasattr(sink, attr)
        )
        dunder_missing = sorted(
            attr
            for attr in required
            if attr.startswith("__") and not hasattr(type(sink), attr)
        )
        self.assertEqual(
            (missing, dunder_missing),
            ([], []),
            "py-cord 受信パイプラインが要求する属性が不足: "
            + ", ".join(missing + dunder_missing),
        )


if __name__ == "__main__":
    unittest.main()
