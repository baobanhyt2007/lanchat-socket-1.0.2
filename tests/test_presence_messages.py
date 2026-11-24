"""Presence lines shown when a peer is first discovered.

A peer that starts with --status away must be announced as away; only a peer
that is really online may produce the "is online" line.
"""

import socket
import tempfile
import unittest
from pathlib import Path

from lanchat.app import App
from lanchat.discovery import Peer, PeerEvent


def free_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
    finally:
        sock.close()


class PresenceMessageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = App("Tester", free_port(), 9999, ["127.0.0.1"],
                       Path(self.tmp.name))
        self.lines = []
        self.app.console.show = self.lines.append

    def tearDown(self):
        self.app.server.stop()
        self.tmp.cleanup()

    def event(self, kind, status, previous=None):
        peer = Peer("Minh", "192.168.1.12", 6000, status)
        return PeerEvent(kind, peer, previous)

    def test_first_seen_online_says_online(self):
        self.app.on_peer_event(self.event("online", "online"))
        self.assertEqual(self.lines,
                         ["[*] Minh is online (192.168.1.12)."])

    def test_first_seen_away_is_not_announced_as_online(self):
        self.app.on_peer_event(self.event("online", "away"))
        self.assertEqual(self.lines,
                         ["[*] Minh is away (192.168.1.12)."])

    def test_status_change_uses_now(self):
        self.app.on_peer_event(self.event("status", "online", "away"))
        self.assertEqual(self.lines, ["[*] Minh is now online."])


if __name__ == "__main__":
    unittest.main()
