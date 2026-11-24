"""End-to-end tests: real TCP sockets, ChatServer, ChatSession, files."""

import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path

from lanchat import protocol
from lanchat.chat import ChatHistory, ChatServer, ChatSession, FileService
from lanchat.discovery import PeerTable


def free_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


class FakeConsole(object):
    def __init__(self):
        self.lines = []
        self.lock = threading.Lock()

    def show(self, line=""):
        with self.lock:
            self.lines.append(line)


class FakeApp(object):
    """The smallest object ChatServer/ChatSession need."""

    def __init__(self, port, downloads):
        self.name = "Tester"
        self.tcp_port = port
        self.console = FakeConsole()
        self.history = ChatHistory()
        self.peers = PeerTable()
        self.messages = []
        self.message_event = threading.Event()
        self.session = ChatSession(self)
        self.files = FileService(
            self.name, port, downloads, on_notice=self.console.show)

    def on_peer_seen(self, name, ip, tcp_port):
        self.peers.update(name, ip, tcp_port)

    def on_chat_message(self, peer_name, text):
        self.messages.append((peer_name, text))
        self.message_event.set()


class ServerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.downloads = Path(self.temp.name)
        self.port = free_port()
        self.app = FakeApp(self.port, self.downloads)
        self.server = ChatServer(self.app, self.port)
        self.server.start()

    def tearDown(self):
        self.server.stop()
        self.server.join(timeout=2.0)
        self.app.session.close_all()
        self.temp.cleanup()

    def connect(self):
        client = socket.create_connection(("127.0.0.1", self.port), timeout=3.0)
        client.settimeout(3.0)
        return client

    def test_chat_message_is_received_and_bye_closes(self):
        client = self.connect()
        client.sendall(protocol.encode_hi("Minh", 6000))
        client.sendall(protocol.encode_msg("Chào Quan"))
        self.assertTrue(self.app.message_event.wait(2.0))
        self.assertEqual(self.app.messages, [("Minh", "Chào Quan")])
        self.assertEqual(self.app.session.partner, "Minh")
        client.sendall(protocol.encode_bye())
        deadline = time.time() + 2.0
        while self.app.session.partner is not None and time.time() < deadline:
            time.sleep(0.02)
        self.assertIsNone(self.app.session.partner)
        client.close()

    def test_file_connection_is_saved_in_downloads(self):
        payload = b"0123456789" * 2000
        client = self.connect()
        client.sendall(protocol.encode_hi(
            "Minh", 6000, protocol.PURPOSE_FILE))
        client.sendall(
            protocol.encode_file_header("payload.bin", len(payload)) + payload)
        deadline = time.time() + 3.0
        saved = self.downloads / "payload.bin"
        while not saved.exists() and time.time() < deadline:
            time.sleep(0.02)
        self.assertTrue(saved.exists(), "file was not saved")
        self.assertEqual(saved.read_bytes(), payload)
        client.close()

    def test_garbage_first_frame_is_rejected_without_crash(self):
        client = self.connect()
        client.sendall(b"NOTAFRAME|")
        self.assertEqual(client.recv(16), b"")
        client.close()
        # The server is still alive and accepts a new, valid connection.
        client = self.connect()
        client.sendall(protocol.encode_hi("Huy", 6002))
        client.sendall(protocol.encode_msg("still alive"))
        self.assertTrue(self.app.message_event.wait(2.0))
        client.close()

    def test_outgoing_session_can_chat_with_a_peer(self):
        from lanchat.discovery import Peer

        peer_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        peer_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        peer_server.bind(("127.0.0.1", 0))
        peer_server.listen(1)
        peer_port = peer_server.getsockname()[1]
        received = []

        def peer_loop():
            conn, _ = peer_server.accept()
            reader = protocol.FrameReader(conn)
            hi = reader.read_header()
            received.append(("HI", hi.meta["name"], hi.meta["purpose"]))
            msg = reader.read_header()
            received.append(("MSG", reader.read_text(msg.meta["length"])))
            conn.sendall(protocol.encode_msg("reply from Minh"))
            try:
                reader.read_header()  # BYE
            except Exception:
                pass
            conn.close()

        thread = threading.Thread(target=peer_loop, daemon=True)
        thread.start()
        try:
            self.app.session.open(Peer("Minh", "127.0.0.1", peer_port))
            self.app.session.send_text("hello Minh")
            self.assertTrue(self.app.message_event.wait(2.0))
            self.assertEqual(received[0], ("HI", "Tester", "chat"))
            self.assertEqual(received[1], ("MSG", "hello Minh"))
            self.assertEqual(self.app.messages, [("Minh", "reply from Minh")])
            self.app.session.leave()
        finally:
            thread.join(2.0)
            peer_server.close()

    def test_sender_and_server_transfer_a_file(self):
        from lanchat.discovery import Peer

        source = Path(self.temp.name).parent / ("source_%d.bin" % self.port)
        source.write_bytes(b"abcdef" * 5000)
        try:
            peer = Peer("Minh", "127.0.0.1", self.port)
            self.app.files.send_async(source, peer)
            destination = self.downloads / source.name
            deadline = time.time() + 3.0
            while not destination.exists() and time.time() < deadline:
                time.sleep(0.02)
            self.assertTrue(destination.exists(), "file did not arrive")
            self.assertEqual(destination.read_bytes(), source.read_bytes())
        finally:
            try:
                source.unlink()
            except OSError:
                pass



if __name__ == "__main__":
    unittest.main()
