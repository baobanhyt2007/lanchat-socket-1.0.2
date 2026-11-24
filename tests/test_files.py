"""File transfer tests: saving, cleanup on failure, safe and unique names."""

import socket
import tempfile
import unittest
from pathlib import Path

from lanchat import protocol
from lanchat.chat.files import FileService, safe_filename, unique_path
from lanchat.errors import ConnectionClosed


class FakeSink(object):
    def __init__(self):
        self.progress = []
        self.notices = []

    def on_progress(self, direction, name, percent, peer):
        self.progress.append((direction, name, percent))

    def on_notice(self, line):
        self.notices.append(line)


class FileServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.downloads = Path(self.temp.name)
        self.writer, self.reader_sock = socket.socketpair()
        self.reader_sock.settimeout(2.0)
        self.sink = FakeSink()
        self.service = FileService(
            "Tester", 5001, self.downloads,
            on_progress=self.sink.on_progress, on_notice=self.sink.on_notice)

    def tearDown(self):
        for sock in (self.writer, self.reader_sock):
            try:
                sock.close()
            except OSError:
                pass
        self.temp.cleanup()

    def _receive(self):
        reader = protocol.FrameReader(self.reader_sock)
        header = reader.read_header()
        return self.service.receive(
            self.reader_sock, reader, header.meta, "Minh")

    def test_file_is_saved_and_progress_reaches_100(self):
        payload = b"hello file transfer" * 100
        self.writer.sendall(
            protocol.encode_file_header("notes.txt", len(payload)) + payload)
        saved = self._receive()
        self.assertTrue(saved.exists())
        self.assertEqual(saved.read_bytes(), payload)
        self.assertEqual(self.sink.progress[-1][2], 100)
        self.assertFalse(Path(str(saved) + ".part").exists())

    def test_interrupted_transfer_deletes_partial_file(self):
        self.writer.sendall(protocol.encode_file_header("big.bin", 1000))
        self.writer.sendall(b"x" * 10)
        self.writer.close()
        with self.assertRaises((ConnectionClosed, OSError)):
            self._receive()
        leftovers = list(self.downloads.iterdir())
        self.assertEqual(leftovers, [])

    def test_duplicate_name_gets_a_number(self):
        existing = self.downloads / "report.pdf"
        existing.write_bytes(b"old")
        payload = b"new"
        self.writer.sendall(
            protocol.encode_file_header("report.pdf", len(payload)) + payload)
        saved = self._receive()
        self.assertEqual(saved.name, "report (1).pdf")
        self.assertEqual(existing.read_bytes(), b"old")

    def test_safe_filename_blocks_traversal_and_reserved_names(self):
        self.assertEqual(safe_filename("../../evil.txt"), "evil.txt")
        self.assertEqual(safe_filename("..\\..\\evil.txt"), "evil.txt")
        self.assertEqual(safe_filename("CON.txt"), "file_CON.txt")
        self.assertEqual(safe_filename("a:b?.txt"), "a_b_.txt")
        self.assertEqual(safe_filename(""), "received_file")
        self.assertEqual(safe_filename("   "), "received_file")

    def test_unique_path_helper(self):
        first = self.downloads / "a.txt"
        first.write_text("x")
        self.assertEqual(unique_path(first).name, "a (1).txt")

    def test_unique_path_avoids_an_active_part_file(self):
        active = self.downloads / "inflight.bin"
        Path(str(active) + ".part").write_bytes(b"partial")
        self.assertEqual(unique_path(active).name, "inflight (1).bin")


if __name__ == "__main__":
    unittest.main()
