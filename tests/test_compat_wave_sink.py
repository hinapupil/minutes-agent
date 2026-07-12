from __future__ import annotations

import unittest
from types import SimpleNamespace

from bot.commands.recording import CompatWaveSink


class CompatWaveSinkTest(unittest.TestCase):
    def test_write_extracts_pcm_and_keys_by_user_id(self) -> None:
        sink = CompatWaveSink()
        data = SimpleNamespace(pcm=b"\x01\x02", packet=SimpleNamespace(ssrc=999))
        user = SimpleNamespace(id=12345)

        sink.write(data, user)
        sink.write(data, user)

        self.assertIn(12345, sink.audio_data)
        buffer = sink.audio_data[12345].file
        buffer.seek(0)
        self.assertEqual(buffer.read(), b"\x01\x02\x01\x02")

    def test_write_falls_back_to_ssrc_when_user_unknown(self) -> None:
        sink = CompatWaveSink()
        data = SimpleNamespace(pcm=b"\xaa", packet=SimpleNamespace(ssrc=777))

        sink.write(data, None)

        self.assertIn(777, sink.audio_data)

    def test_write_ignores_empty_pcm(self) -> None:
        sink = CompatWaveSink()
        data = SimpleNamespace(pcm=b"", packet=SimpleNamespace(ssrc=1))

        sink.write(data, SimpleNamespace(id=1))

        self.assertEqual(sink.audio_data, {})

    def test_router_contract_attributes_exist(self) -> None:
        sink = CompatWaveSink()

        # 2.8 の SinkEventRouter が要求する契約
        self.assertEqual(sink.__sink_listeners__, [])
        self.assertEqual(list(sink.walk_children()), [])
        self.assertEqual(list(sink.walk_children(with_self=True)), [sink])


if __name__ == "__main__":
    unittest.main()
