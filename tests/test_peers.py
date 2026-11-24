"""Peer table tests: online/offline, status changes, timeout, name lookup."""

import unittest

from lanchat.discovery import PeerTable, parse_presence


class PeerTableTests(unittest.TestCase):
    def test_first_update_is_online_and_refresh_is_silent(self):
        table = PeerTable(timeout=10, clock=lambda: 100.0)
        events = table.update("Minh", "192.168.1.12", 6000, "online", now=100.0)
        self.assertEqual([event.kind for event in events], ["online"])
        events = table.update("Minh", "192.168.1.12", 6000, "online", now=101.0)
        self.assertEqual(events, [])

    def test_status_change_emits_event(self):
        table = PeerTable(timeout=10, clock=lambda: 100.0)
        table.update("Minh", "192.168.1.12", 6000, "online", now=100.0)
        events = table.update("Minh", "192.168.1.12", 6000, "away", now=101.0)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].kind, "status")
        self.assertEqual(events[0].previous_status, "online")
        self.assertEqual(events[0].peer.status, "away")

    def test_timeout_removes_peer_exactly_after_10_seconds(self):
        table = PeerTable(timeout=10, clock=lambda: 100.0)
        table.update("Minh", "192.168.1.12", 6000, "online", now=100.0)
        self.assertEqual(table.sweep(now=110.0), [])
        events = table.sweep(now=110.1)
        self.assertEqual([event.kind for event in events], ["offline"])
        self.assertIsNone(table.get("Minh"))

    def test_activity_postpones_timeout(self):
        table = PeerTable(timeout=10, clock=lambda: 100.0)
        table.update("Minh", "192.168.1.12", 6000, "online", now=100.0)
        table.update("Minh", "192.168.1.12", 6000, "online", now=108.0)
        self.assertEqual(table.sweep(now=115.0), [])
        self.assertEqual(len(table), 1)

    def test_find_by_name_number_and_prefix(self):
        table = PeerTable()
        table.update("Minh", "192.168.1.12", 6000)
        table.update("Lan", "192.168.1.15", 5000)
        table.update("Huy", "192.168.1.20", 5000)
        self.assertEqual(table.find("Minh").ip, "192.168.1.12")
        self.assertEqual(table.find("2").name, "Lan")
        self.assertEqual(table.find("mi").name, "Minh")
        self.assertIsNone(table.find("99"))
        self.assertIsNone(table.find("zzz"))

    def test_ambiguous_prefix_returns_none(self):
        table = PeerTable()
        table.update("Minh", "192.168.1.12", 6000)
        table.update("Minh2", "192.168.1.13", 6000)
        self.assertIsNone(table.find("min"))

    def test_parse_presence(self):
        self.assertEqual(
            parse_presence(b"HELLO|Quan|5000|online"),
            ("Quan", 5000, "online"))
        self.assertIsNone(parse_presence(b"HELLO|Quan|online"))
        self.assertIsNone(parse_presence(b"HELLO|Quan|notaport|online"))
        self.assertIsNone(parse_presence(b"HELLO|Quan|70000|online"))
        self.assertIsNone(parse_presence(b"PING|Quan|5000|online"))


if __name__ == "__main__":
    unittest.main()
