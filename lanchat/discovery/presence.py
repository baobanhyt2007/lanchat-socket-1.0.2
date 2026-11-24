"""UDP presence broadcasting (one datagram every 3 seconds)."""

import socket
import threading

from .. import config
from ..protocol import clean_name


class PresenceService(threading.Thread):
    """Keeps sending HELLO|name|tcp_port|status to the LAN.

    A separate ephemeral socket is used for sending so the discovery listener
    can keep port 9999 exclusively for receiving. `set_status()` wakes the
    thread immediately: the new status is on the wire before the next prompt.
    """

    def __init__(self, name, tcp_port, udp_port=config.UDP_DISCOVERY_PORT,
                 broadcast_addrs=None, interval=config.BROADCAST_INTERVAL,
                 status="online"):
        threading.Thread.__init__(self, daemon=True, name="udp-presence")
        self.peer_name = clean_name(name)
        self.tcp_port = int(tcp_port)
        self.udp_port = int(udp_port)
        self.broadcast_addrs = list(broadcast_addrs or [config.DEFAULT_BROADCAST])
        self.interval = float(interval)
        self._lock = threading.Lock()
        self._status = status
        self._stop_event = threading.Event()
        self._wake = threading.Event()

    @property
    def status(self):
        with self._lock:
            return self._status

    def set_status(self, status):
        if status not in ("online", "away"):
            raise ValueError("status must be 'online' or 'away'")
        with self._lock:
            self._status = status
        self._wake.set()

    def stop(self):
        self._stop_event.set()
        self._wake.set()

    def payload(self):
        return ("HELLO|%s|%d|%s" % (
            self.peer_name, self.tcp_port, self.status)).encode("utf-8")

    def _send_once(self, sock):
        data = self.payload()
        for addr in self.broadcast_addrs:
            try:
                sock.sendto(data, (addr, self.udp_port))
            except OSError:
                # A dead interface must not kill the presence thread.
                continue

    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.bind(("", 0))
            while not self._stop_event.is_set():
                self._send_once(sock)
                self._wake.wait(self.interval)
                self._wake.clear()
        finally:
            try:
                sock.close()
            except OSError:
                pass
