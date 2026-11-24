"""App: wires the four services together and owns the shared state.

Threads:
    main         keyboard loop + command dispatch
    udp-presence sends HELLO every 3 s
    udp-listener receives HELLO, updates PeerTable, sweeps timeouts
    tcp-acceptor accepts connections, one handler thread per connection
    chat-rx-*    one per outgoing chat connection
    file-tx-*    one per outgoing file transfer

Shared state: PeerTable, ChatHistory, ChatSession and Console each protect
themselves with their own lock; no locking order is shared between them, so a
slow disk write can never block the keyboard.
"""

import os
import sys
import threading
from pathlib import Path

from . import config
from .chat import ChatHistory, ChatServer, ChatSession, FileService
from .discovery import (
    STATUS_AWAY, DiscoveryListener, PeerTable, PresenceService)
from .errors import ConnectionClosed, LanChatError, PeerOffline, ProtocolError
from .protocol import clean_name
from .ui import Console, handle_line as run_command

BANNER = "\n".join([
    "  _      _    _  _    ___ _           _   ",
    " | |    /_\\  | \\| |  / __| |_  __ _| |_ ",
    " | |__ / _ \\ | .` | | (__| ' \\/ _` |  _|",
    " |____/_/ \\_\\|_|\\_|  \\___|_||_\\__,_|\\__|",
    "  LAN Chat & File Sharing  (UDP + TCP)",
])


class App(object):
    def __init__(self, name, tcp_port=config.DEFAULT_TCP_PORT,
                 udp_port=config.UDP_DISCOVERY_PORT,
                 broadcast_addrs=None,
                 download_dir=config.DOWNLOAD_DIR,
                 status="online"):
        self.name = clean_name(name)
        self.tcp_port = int(tcp_port)
        self.udp_port = int(udp_port)
        self.broadcast_addrs = list(broadcast_addrs or [config.DEFAULT_BROADCAST])
        self.download_dir = Path(download_dir)
        self._shutdown = threading.Event()

        self.console = Console()
        self.history = ChatHistory()
        self.peers = PeerTable()
        self.files = FileService(
            self.name, self.tcp_port, self.download_dir,
            on_progress=self.on_file_progress,
            on_notice=self.console.show)
        self.session = ChatSession(self)
        self.server = ChatServer(self, self.tcp_port)   # binds the TCP port
        self.presence = PresenceService(
            self.name, self.tcp_port, self.udp_port,
            self.broadcast_addrs, status=status)
        self.listener = DiscoveryListener(
            self.peers, self.on_discovery_event,
            self.name, self.tcp_port, self.udp_port)

    # -- lifecycle ---------------------------------------------------------
    def dispatch_line(self, line):
        """Keyboard callback: Console calls this with exactly one argument."""
        run_command(self, line)

    def start(self):
        self._print_startup()
        self.server.start()
        self.presence.start()
        self.listener.start()
        self.console.run(self.dispatch_line)

    def shutdown(self):
        if self._shutdown.is_set():
            return
        self._shutdown.set()
        self.session.close_all()
        for service in (self.presence, self.listener, self.server):
            try:
                service.stop()
            except Exception:
                pass
        for service in (self.presence, self.listener, self.server):
            if service is not threading.current_thread() and service.is_alive():
                service.join(timeout=1.0)
        self.console.stop()

    def _print_startup(self):
        self.console.show(BANNER)
        self.console.show("[*] %s | TCP %d | UDP %d | status %s" % (
            self.name, self.tcp_port, self.udp_port, self.presence.status))
        self.console.show("[*] Broadcasting to: %s" % ", ".join(
            "%s:%d" % (a, self.udp_port) for a in self.broadcast_addrs))
        self.console.show("[*] Downloads folder: %s" % self.download_dir)
        self.console.show("[*] Type /help for the command list.")

    # -- discovery callbacks ----------------------------------------------
    def on_discovery_event(self, kind, payload):
        if kind == "peer":
            self.on_peer_event(payload)
        elif kind == "error":
            self.console.show("[!] Discovery: %s" % payload)

    def on_peer_event(self, event):
        peer = event.peer
        if event.kind == "online":
            if peer.status == STATUS_AWAY:
                self.console.show(
                    "[*] %s is away (%s)." % (peer.name, peer.ip))
            else:
                self.console.show(
                    "[*] %s is online (%s)." % (peer.name, peer.ip))
        elif event.kind == "offline":
            self.console.show("[*] %s is offline." % peer.name)
            self.session.on_peer_offline(peer.name)
        elif event.kind == "status":
            self.console.show("[*] %s is now %s." % (peer.name, peer.status))

    def on_peer_seen(self, name, ip, tcp_port):
        """A TCP connection proves the peer is alive even if UDP was lost."""
        if name == self.name and int(tcp_port) == self.tcp_port:
            return
        current = self.peers.get(name)
        status = current.status if current is not None else "online"
        for event in self.peers.update(name, ip, tcp_port, status):
            self.on_peer_event(event)

    # -- chat callbacks ----------------------------------------------------
    def on_chat_message(self, peer_name, text):
        unread = self.history.add(peer_name, text, author=peer_name)
        if self.session.partner == peer_name:
            self.console.show("[%s] %s" % (peer_name, text))
            self.history.mark_read(peer_name)
        else:
            self.console.show("[*] New message from %s (%d unread)"
                              % (peer_name, unread))

    def send_chat_message(self, text):
        partner = self.session.partner
        if not partner:
            self.console.show(
                "[!] No active chat. Use /list, then /chat <name>.")
            return
        text = (text or "").strip()
        if not text:
            return
        try:
            self.session.send_text(text)
        except (PeerOffline, ConnectionClosed, ProtocolError, OSError) as exc:
            self.console.show("[!] Cannot send message: %s" % exc)
            return
        self.history.add(partner, text, author=self.name)
        self.history.mark_read(partner)
        self.console.show("[%s] %s" % (self.name, text))

    # -- commands ----------------------------------------------------------
    def show_peer_list(self):
        peers = self.peers.snapshot()
        if not peers:
            self.console.show(
                "[*] No peers online yet. Start another instance with a "
                "different --port on this LAN.")
            return
        self.console.show("[*] Online peers (%d):" % len(peers))
        for index, peer in enumerate(peers, 1):
            self.console.show("  %d. %s" % (index, peer.describe()))

    def start_chat(self, token):
        peer = self.peers.find(token)
        if peer is None:
            self.console.show(
                "[!] No peer matches %r. Try /list." % token)
            return
        if peer.name == self.name and peer.tcp_port == self.tcp_port:
            self.console.show("[!] That is you.")
            return
        try:
            self.session.open(peer)
        except (PeerOffline, OSError) as exc:
            self.console.show("[!] %s" % exc)

    def send_file(self, path_text):
        if not self.session.partner:
            self.console.show(
                "[!] No active chat. Use /chat <name> before /send.")
            return
        raw = path_text.strip().strip('"').strip("'")
        path = Path(os.path.expanduser(raw))
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        if not path.is_file():
            self.console.show("[!] File not found: %s" % path)
            return
        peer = self.peers.get(self.session.partner)
        if peer is None:
            self.console.show(
                "[!] %s is not online anymore." % self.session.partner)
            return
        self.files.send_async(path, peer)

    def set_status(self, status):
        if status not in ("online", "away"):
            self.console.show("[!] Usage: /status online|away")
            return
        self.presence.set_status(status)
        self.console.show("[*] Status set to %s." % status)

    def on_file_progress(self, direction, filename, percent, peer_name):
        verb = "Sending" if direction == "send" else "Receiving"
        done = " Done." if percent >= 100 else ""
        self.console.show("[*] %s %s ... %d%%%s"
                          % (verb, filename, percent, done))
