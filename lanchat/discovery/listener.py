"""UDP listener: receives presence datagrams and updates the peer table."""

import socket
import threading
import time

from .. import config
from .peers import STATUSES


def parse_presence(data):
    """Return (name, tcp_port, status) or None for a malformed datagram."""
    try:
        text = data.decode("utf-8", "replace").strip()
    except Exception:
        return None
    parts = text.split("|")
    if len(parts) != 4 or parts[0] != "HELLO":
        return None
    name, port_text, status = parts[1], parts[2], parts[3]
    if not name or len(name) > config.NAME_MAX_LEN:
        return None
    try:
        port = int(port_text)
    except ValueError:
        return None
    if not 0 < port < 65536:
        return None
    if status not in STATUSES:
        status = "online"
    return name, port, status


class DiscoveryListener(threading.Thread):
    """One thread per peer: wait for UDP packets, then sweep old peers."""

    def __init__(self, peers, on_event, self_name, self_port,
                 udp_port=config.UDP_DISCOVERY_PORT,
                 sweep_interval=config.SWEEP_INTERVAL):
        threading.Thread.__init__(self, daemon=True, name="udp-listener")
        self.peers = peers
        self.on_event = on_event
        self.self_name = self_name
        self.self_port = int(self_port)
        self.udp_port = int(udp_port)
        self.sweep_interval = float(sweep_interval)
        self._stop_event = threading.Event()
        self._sock = None

    def stop(self):
        self._stop_event.set()
        sock = self._sock
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    def _make_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Several instances on ONE machine must be able to bind the same port.
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass
        sock.bind(("", self.udp_port))
        sock.settimeout(config.UDP_POLL_TIMEOUT)
        return sock

    def run(self):
        try:
            sock = self._make_socket()
        except OSError as exc:  # pragma: no cover - environment dependent
            self.on_event("error", "UDP port %d: %s" % (self.udp_port, exc))
            return
        self._sock = sock
        last_sweep = time.time()
        try:
            while not self._stop_event.is_set():
                try:
                    data, addr = sock.recvfrom(2048)
                except socket.timeout:
                    pass
                except OSError:
                    if self._stop_event.is_set():
                        break
                    continue
                else:
                    parsed = parse_presence(data)
                    if parsed is not None:
                        name, port, status = parsed
                        # Ignore our own broadcast (same name, same TCP port).
                        if not (name == self.self_name and port == self.self_port):
                            for event in self.peers.update(
                                    name, addr[0], port, status):
                                self.on_event("peer", event)

                now = time.time()
                if now - last_sweep >= self.sweep_interval:
                    last_sweep = now
                    for event in self.peers.sweep(now):
                        self.on_event("peer", event)
        finally:
            try:
                sock.close()
            except OSError:
                pass


def make_listener_socket(udp_port):  # pragma: no cover - helper for scripts
    """Create a reusable broadcast socket (used by ad-hoc test scripts)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(socket, "SO_REUSEPORT"):
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except OSError:
            pass
    sock.bind(("", udp_port))
    return sock
