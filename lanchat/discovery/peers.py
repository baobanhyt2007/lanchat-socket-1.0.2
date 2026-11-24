"""Discovery: the shared peer table.

The table is written by the UDP listener thread and read by the console
thread and the chat code, therefore every public method takes the same lock.
`clock` is injectable so unit tests can simulate 10 seconds of silence
without sleeping.
"""

import threading
import time

from .. import config

STATUS_ONLINE = "online"
STATUS_AWAY = "away"
STATUSES = (STATUS_ONLINE, STATUS_AWAY)


class Peer(object):
    __slots__ = ("name", "ip", "tcp_port", "status", "last_seen")

    def __init__(self, name, ip, tcp_port, status=STATUS_ONLINE, last_seen=None):
        self.name = name
        self.ip = ip
        self.tcp_port = int(tcp_port)
        self.status = status
        self.last_seen = time.time() if last_seen is None else last_seen

    def __repr__(self):  # pragma: no cover - debugging aid
        return "Peer(%r, %r, %r, %r)" % (
            self.name, self.ip, self.tcp_port, self.status)

    def describe(self, now=None):
        now = time.time() if now is None else now
        age = max(0, int(now - self.last_seen))
        return "%-12s %-15s tcp/%-5d  %-6s  %2ds" % (
            self.name, self.ip, self.tcp_port, self.status, age)


class PeerEvent(object):
    """Something worth printing: online / offline / status / update."""

    __slots__ = ("kind", "peer", "previous_status")

    def __init__(self, kind, peer, previous_status=None):
        self.kind = kind
        self.peer = peer
        self.previous_status = previous_status

    def __repr__(self):  # pragma: no cover - debugging aid
        return "PeerEvent(%r, %r)" % (self.kind, self.peer)


class PeerTable(object):
    def __init__(self, timeout=config.PEER_TIMEOUT, clock=time.time):
        self._lock = threading.RLock()
        self._peers = {}
        self._timeout = timeout
        self._clock = clock

    # -- writes ------------------------------------------------------------
    def update(self, name, ip, tcp_port, status=STATUS_ONLINE, now=None):
        """Insert or refresh a peer, returning the events to display."""
        now = self._clock() if now is None else now
        if status not in STATUSES:
            status = STATUS_ONLINE
        events = []
        with self._lock:
            peer = self._peers.get(name)
            if peer is None:
                peer = Peer(name, ip, int(tcp_port), status, now)
                self._peers[name] = peer
                events.append(PeerEvent("online", peer))
            else:
                changed_address = (peer.ip != ip or peer.tcp_port != int(tcp_port))
                previous = peer.status
                peer.ip = ip
                peer.tcp_port = int(tcp_port)
                peer.last_seen = now
                if previous != status:
                    peer.status = status
                    events.append(PeerEvent("status", peer, previous))
                elif changed_address:
                    events.append(PeerEvent("update", peer))
            return events

    def sweep(self, now=None):
        """Remove peers not heard from within the timeout."""
        now = self._clock() if now is None else now
        with self._lock:
            dead = [p for p in self._peers.values()
                    if now - p.last_seen > self._timeout]
            for peer in dead:
                del self._peers[peer.name]
            return [PeerEvent("offline", p) for p in dead]

    def remove(self, name):
        with self._lock:
            return self._peers.pop(name, None)

    def clear(self):
        with self._lock:
            self._peers.clear()

    # -- reads -------------------------------------------------------------
    def snapshot(self):
        with self._lock:
            peers = list(self._peers.values())
        return sorted(peers, key=lambda p: p.name.lower())

    def get(self, name):
        with self._lock:
            return self._peers.get(name)

    def find(self, token):
        """Resolve '/chat <name|number>' to a Peer (or None when ambiguous)."""
        token = (token or "").strip()
        if not token:
            return None
        peers = self.snapshot()
        if token.isdigit():
            index = int(token) - 1
            if 0 <= index < len(peers):
                return peers[index]
            return None
        low = token.lower()
        for peer in peers:
            if peer.name.lower() == low:
                return peer
        matches = [p for p in peers if p.name.lower().startswith(low)]
        if len(matches) == 1:
            return matches[0]
        return None

    def __len__(self):
        with self._lock:
            return len(self._peers)
