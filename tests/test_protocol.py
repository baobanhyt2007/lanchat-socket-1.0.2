"""Protocol/framing tests: partial reads, two frames at once, UTF-8 sizes."""

import socket
import threading
import unittest

from lanchat import protocol
from lanchat.errors import ProtocolError


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.writer, self.reader_sock = socket.socketpair()
        self.writer.settimeout(2.0)
        self.reader_sock.settimeout(2.0)
        self.reader = protocol.FrameReader(self.reader_sock)

    def tearDown(self):
        for sock in (self.writer, self.reader_sock):
            try:
                sock.close()
            except OSError:
                pass

    def test_msg_uses_byte_length_not_character_count(self):
        text = "Chào Minh, sẵn sàng demo chưa?"
        self.writer.sendall(protocol.encode_msg(text))
        header = self.reader.read_header()
        self.assertEqual(header.type, protocol.TYPE_MSG)
        self.assertEqual(header.meta["length"], len(text.encode("utf-8")))
        self.assertNotEqual(header.meta["length"], len(text))
        self.assertEqual(self.reader.read_text(header.meta["length"]), text)

    def test_two_frames_in_one_recv(self):
        payload = protocol.encode_msg("one") + protocol.encode_msg("two")
        self.writer.sendall(payload)
        first = self.reader.read_header()
        self.assertEqual(self.reader.read_text(first.meta["length"]), "one")
        second = self.reader.read_header()
        self.assertEqual(self.reader.read_text(second.meta["length"]), "two")

    def test_fragmented_frame(self):
        payload = protocol.encode_msg("xin chào")
        started = threading.Event()

        def drip():
            started.set()
            for index in range(len(payload)):
                self.writer.sendall(payload[index:index + 1])

        thread = threading.Thread(target=drip)
        thread.start()
        started.wait(1.0)
        header = self.reader.read_header()
        self.assertEqual(self.reader.read_text(header.meta["length"]), "xin chào")
        thread.join(2.0)
        self.assertFalse(thread.is_alive())

    def test_file_header_escapes_pipe_and_accents(self):
        name = "báo cáo | final.pdf"
        self.writer.sendall(protocol.encode_file_header(name, 5) + b"hello")
        header = self.reader.read_header()
        self.assertEqual(header.type, protocol.TYPE_FILE)
        self.assertEqual(header.meta["name"], name)
        self.assertEqual(header.meta["size"], 5)
        self.assertEqual(b"".join(self.reader.iter_payload(5)), b"hello")

    def test_bye(self):
        self.writer.sendall(protocol.encode_bye())
        header = self.reader.read_header()
        self.assertEqual(header.type, protocol.TYPE_BYE)

    def test_hi_carries_connection_purpose(self):
        self.writer.sendall(protocol.encode_hi(
            "Quan", 5000, protocol.PURPOSE_FILE))
        header = self.reader.read_header()
        self.assertEqual(header.type, protocol.TYPE_HI)
        self.assertEqual(header.meta["name"], "Quan")
        self.assertEqual(header.meta["port"], 5000)
        self.assertEqual(header.meta["purpose"], protocol.PURPOSE_FILE)

    def test_unknown_hi_purpose_is_rejected(self):
        self.writer.sendall(b"HI|Quan|5000|nonsense|")
        with self.assertRaises(ProtocolError):
            self.reader.read_header()

    def test_unknown_frame_type_is_rejected(self):
        self.writer.sendall(b"GARBAGE|")
        with self.assertRaises(ProtocolError):
            self.reader.read_header()

    def test_absurd_header_is_rejected(self):
        self.writer.sendall(b"A" * 5000)
        with self.assertRaises(ProtocolError):
            self.reader.read_header()

    def test_negative_message_length_is_rejected(self):
        self.writer.sendall(b"MSG|-5|")
        with self.assertRaises(ProtocolError):
            self.reader.read_header()

    def test_recv_exact_helper(self):
        self.writer.sendall(b"abcdef")
        self.assertEqual(protocol.recv_exact(self.reader_sock, 4), b"abcd")


if __name__ == "__main__":
    unittest.main()
