"""Preview request budgeting and completed-cache reuse without real CDN traffic."""

import unittest
from unittest.mock import MagicMock, patch
from songranker import apple_access as media


class PreviewDeliveryTests(unittest.TestCase):
    def test_ten_song_rotation_fits_the_existing_gate(self):
        clock = [0.0]
        gate = media.RequestGate(18, 0.5, clock=lambda: clock[0])
        for second in range(0, 101, 10):
            clock[0] = second
            gate.admit((second // 10 % 10, "shelves"))
        self.assertLessEqual(len(gate.starts), 6)
        # Rapid manual jumps still respect the gate; limits are not increased.
        gate = media.RequestGate(18, 0.5, clock=lambda: clock[0])
        for i in range(18):
            clock[0] = 200 + i * 0.5
            gate.admit((i, "rapid"))
        clock[0] = 210
        with self.assertRaises(media.AppleRequestError) as blocked:
            gate.admit((19, "rapid"))
        self.assertEqual(blocked.exception.state, "throttled")

    def test_cached_replay_and_ranges_bypass_upstream_even_during_cooldown(self):
        body = b"complete preview bytes"
        upstream = MagicMock(
            status_code=200,
            headers={"Content-Type": "audio/mp4", "Content-Length": str(len(body))},
        )
        upstream.iter_content.return_value = iter([body])
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = {
            "audio_url": "https://audio-ssl.itunes.apple.com/test.m4a"
        }
        gate = media.RequestGate(18, 0.5)
        cache = media.PreviewMemoryCache()
        with patch.object(media, "get_db_connection", return_value=conn), patch.object(
            media, "preview_gate", gate
        ), patch.object(media, "preview_cache", cache), patch.object(
            media.requests, "get", return_value=upstream
        ) as get:
            client = media.app.test_client()
            url = "/api/previews/1?page=shelves_test&play=shelves_test"
            first = client.get(url)
            self.assertEqual(first.data, body)
            self.assertEqual(first.headers["X-Preview-Cache"], "miss")
            gate.block(60)
            replay = client.get(url)
            self.assertEqual(replay.data, body)
            self.assertEqual(replay.headers["X-Preview-Cache"], "hit")
            part = client.get(url, headers={"Range": "bytes=3-8"})
            self.assertEqual(part.status_code, 206)
            self.assertEqual(part.data, body[3:9])
            self.assertEqual(get.call_count, 1)
            upstream.close.assert_called()

    def test_cache_holds_a_full_round_and_expires_without_disk_storage(self):
        clock = [0.0]
        cache = media.PreviewMemoryCache(clock=lambda: clock[0])
        for i in range(10):
            cache.put(("page", i, "url"), b"audio", "audio/mp4")
        self.assertTrue(all(cache.get(("page", i, "url")) for i in range(10)))
        clock[0] = 101
        self.assertIsNotNone(cache.get(("page", 0, "url")))
        clock[0] = 601
        self.assertIsNone(cache.get(("page", 0, "url")))
