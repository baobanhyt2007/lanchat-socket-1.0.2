"""Chat session: one TCP connection per peer, plus the current partner.

The session owns every chat socket:
  * /chat <peer>       -> open (or reuse) the connection, become the partner
  * /leave             -> send BYE, close, clear the partner
  * incoming message   -> displayed if it is the partner, otherwise counted
                          as unread and announced

Duplicate-connection rule (both peers may type /chat at the same time):
the connection initiated by the lexicographically smaller name wins. Both
sides apply the same rule, so they always converge on the same socket.
"""

import socket
import threading

from .. import config, protocol
from ..errors import ConnectionClosed, PeerOffline, ProtocolError


class ChatConnection(object):
    def __init__(self, peer_name, sock, reader, direction):
        self.peer_name = peer_name
        self.sock = sock
        self.reader = reader
        self.direction = direction          # "out" or "in"
        self.send_lock = threading.Lock()
        self.closed = False
        self.peer_ip = None
        self.peer_port = None

    def send(self, data):
        if self.closed:
            raise ConnectionClosed("connection already closed")
        with self.send_lock:
            self.sock.sendall(data)

    def close(self, send_bye=False):
        if self.closed:
            return
        if send_bye:
            try:
                with self.send_lock:
                    self.sock.sendall(protocol.encode_bye())
            except OSError:
                pass
        self.closed = True
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass


class ChatSession(object):
    def __init__(self, app):
        self._app = app
        self._self_name = app.name
        self._self_port = app.tcp_port
        self._lock = threading.RLock()
        self._conns = {}                    # peer name -> ChatConnection
        self._partner = None
        self._stopping = threading.Event()

    # -- helpers -----------------------------------------------------------
    @property
    def partner(self):
        with self._lock:
            return self._partner

    def connection_count(self):
        with self._lock:
            return len(self._conns)

    def has_connection(self, peer_name):
        with self._lock:
            conn = self._conns.get(peer_name)
            return conn is not None and not conn.closed

    def _prefer_incoming(self, peer_name):
        """True when I am the larger name: their outgoing connection wins."""
        return self._self_name > peer_name

    # -- connection registry ----------------------------------------------
    def _install(self, conn):
        """Register a connection, resolving duplicates. False = rejected."""
        with self._lock:
            old = self._conns.get(conn.peer_name)
            if old is None or old is conn:
                self._conns[conn.peer_name] = conn
                return True
            # Same direction: keep the newest connection.
            if old.direction == conn.direction:
                old.close(send_bye=True)
            elif conn.direction == "in" and old.direction == "out":
                if self._prefer_incoming(conn.peer_name):
                    old.close(send_bye=True)
                else:
                    return False
            elif conn.direction == "out" and old.direction == "in":
                if not self._prefer_incoming(conn.peer_name):
                    old.close(send_bye=True)
                else:
                    return False
            self._conns[conn.peer_name] = conn
            return True

    def _drop(self, conn, reason):
        with self._lock:
            is_current = self._conns.get(conn.peer_name) is conn
            if is_current:
                del self._conns[conn.peer_name]
            was_partner = self._partner == conn.peer_name
            if is_current and was_partner:
                self._partner = None
        if not is_current:
            return
        if reason == "bye":
            self._app.console.show("[*] %s left the chat." % conn.peer_name)
        elif reason:
            self._app.console.show(
                "[!] Connection with %s lost: %s" % (conn.peer_name, reason))

    # -- partner -----------------------------------------------------------
    def set_partner(self, peer_name, reason="connected", peer=None):
        with self._lock:
            self._partner = peer_name
            unread = self._app.history.unread_count(peer_name)
            self._app.history.mark_read(peer_name)
            history = self._app.history.messages(peer_name)
        if peer is None:
            peer = self._app.peers.get(peer_name)
        if reason == "incoming":
            self._app.console.show(
                "[*] %s started a chat with you. You are now chatting with %s."
                % (peer_name, peer_name))
        elif reason == "reuse":
            self._app.console.show("[*] Switched to %s." % peer_name)
        elif peer is not None:
            self._app.console.show(
                "[*] Connected to %s (%s:%d)." % (
                    peer_name, peer.ip, peer.tcp_port))
        else:
            self._app.console.show("[*] Chatting with %s." % peer_name)
        if unread > 0:
            self._app.console.show(
                "[*] %d unread message(s) from %s:" % (unread, peer_name))
            for line in history[-unread:]:
                self._app.console.show("   " + line)

    def on_peer_offline(self, peer_name):
        if self.partner == peer_name:
            self._app.console.show(
                "[!] %s is offline now; the chat will close when TCP notices."
                % peer_name)

    # -- outgoing ----------------------------------------------------------
    def open(self, peer):
        with self._lock:
            existing = self._conns.get(peer.name)
        if existing is not None and not existing.closed:
            # The smaller name always wants its own outgoing connection;
            # a larger name happily reuses the incoming one.
            reuse = (existing.direction == "out"
                     or self._prefer_incoming(peer.name))
            if reuse:
                self.set_partner(peer.name, reason="reuse", peer=peer)
                return
        try:
            sock = socket.create_connection(
                (peer.ip, peer.tcp_port), timeout=config.CONNECT_TIMEOUT)
        except OSError as exc:
            raise PeerOffline("cannot connect to %s (%s:%d): %s" % (
                peer.name, peer.ip, peer.tcp_port, exc))
        sock.settimeout(None)
        try:
            sock.sendall(protocol.encode_hi(
                self._self_name, self._self_port, protocol.PURPOSE_CHAT))
        except OSError as exc:
            try:
                sock.close()
            except OSError:
                pass
            raise PeerOffline("cannot send HI to %s: %s" % (peer.name, exc))

        conn = ChatConnection(peer.name, sock, protocol.FrameReader(sock), "out")
        conn.peer_ip, conn.peer_port = peer.ip, peer.tcp_port
        if not self._install(conn):
            conn.close(send_bye=True)
            self.set_partner(peer.name, reason="reuse", peer=peer)
            return
        threading.Thread(
            target=self._receive_loop, args=(conn, None),
            daemon=True, name="chat-rx-%s" % peer.name).start()
        self.set_partner(peer.name, reason="connected", peer=peer)

    # -- incoming ----------------------------------------------------------
    def attach_incoming(self, sock, reader, peer_name, peer_ip, peer_port,
                        first_header=None):
        """Called from ChatServer after a HI(chat) frame was received."""
        conn = ChatConnection(peer_name, sock, reader, "in")
        conn.peer_ip, conn.peer_port = peer_ip, peer_port
        if not self._install(conn):
            conn.close(send_bye=True)
            self._app.console.show(
                "[*] Ignored duplicate chat connection from %s." % peer_name)
            return

        current = self.partner
        if current is None:
            self.set_partner(peer_name, reason="incoming")
        elif current != peer_name:
            self._app.console.show(
                "[*] %s opened a chat. You are still talking to %s "
                "(/chat %s to switch)." % (peer_name, current, peer_name))
        else:
            self._app.console.show("[*] %s reconnected." % peer_name)

        # Run the receiver loop in the server handler thread that already
        # owns this socket. It returns when the peer says BYE or disconnects.
        self._receive_loop(conn, first_header)

    # -- receiving ---------------------------------------------------------
    def _receive_loop(self, conn, first_header):
        header = first_header
        reason = None
        try:
            while not self._stopping.is_set() and not conn.closed:
                if header is None:
                    header = conn.reader.read_header()
                if header.type == protocol.TYPE_MSG:
                    text = conn.reader.read_text(header.meta["length"])
                    self._app.on_chat_message(conn.peer_name, text)
                elif header.type == protocol.TYPE_BYE:
                    reason = "bye"
                    break
                else:
                    raise ProtocolError(
                        "unexpected %s frame on a chat connection" % header.type)
                header = None
        except ConnectionClosed:
            reason = "peer disconnected"
        except (ProtocolError, OSError) as exc:
            reason = str(exc) or type(exc).__name__
        finally:
            conn.close()
            if self._stopping.is_set():
                reason = None
            self._drop(conn, reason)

    # -- sending -----------------------------------------------------------
    def send_text(self, text):
        name = self.partner
        if not name:
            raise PeerOffline("no active chat partner")
        with self._lock:
            conn = self._conns.get(name)
        if conn is None or conn.closed:
            raise PeerOffline("connection to %s is closed" % name)
        conn.send(protocol.encode_msg(text))

    def leave(self):
        with self._lock:
            name = self._partner
            conn = self._conns.get(name) if name else None
            if name is not None:
                self._conns.pop(name, None)
            self._partner = None
        if conn is not None:
            conn.close(send_bye=True)
        if name is not None:
            self._app.console.show("[*] Chat with %s closed." % name)
        return name

    def close_all(self):
        self._stopping.set()
        with self._lock:
            conns = list(self._conns.values())
            self._conns.clear()
            self._partner = None
        for conn in conns:
            conn.close(send_bye=True)
