"""Application-layer protocol and TCP framing.

Wire format (text header, optional raw payload)
-----------------------------------------------
HI    :  HI|<name>|<tcp_port>|<purpose>|      purpose = chat | file
MSG   :  MSG|<nbytes>|<exactly nbytes of UTF-8 text>
FILE  :  FILE|<quoted filename>|<size>|<exactly size raw bytes>
BYE   :  BYE|

Rules
-----
* Every TCP connection starts with a HI frame so the receiver knows who called
  and which TCP port the caller listens on.
* <nbytes> is the size of the UTF-8 encoding, NOT the number of characters.
  "Chao Minh" on a Vietnamese console can be longer in bytes than in keys.
* <filename> is percent-quoted with urllib.parse.quote(safe="") so a file name
  may contain "|", spaces, accents or slashes without breaking the frame.
* A TCP stream has no message boundaries. FrameReader keeps a buffer, so
  recv() returning half a frame, or two frames at once, is handled correctly.

The parser is deliberately strict: unknown frame types, negative sizes or
headers longer than HEADER_MAX raise ProtocolError and the caller closes that
connection only - the rest of the application keeps running.
"""

import os
from urllib.parse import quote, unquote

from . import config
from .errors import ConnectionClosed, ProtocolError

TYPE_HI = "HI"
TYPE_MSG = "MSG"
TYPE_FILE = "FILE"
TYPE_BYE = "BYE"

PURPOSE_CHAT = "chat"
PURPOSE_FILE = "file"
PURPOSES = (PURPOSE_CHAT, PURPOSE_FILE)

PIPE = b"|"


class Header(object):
    """Type of the next frame plus its parsed metadata."""

    __slots__ = ("type", "meta")

    def __init__(self, ftype, meta=None):
        self.type = ftype
        self.meta = meta or {}

    def __repr__(self):  # pragma: no cover - debugging aid
        return "Header(%r, %r)" % (self.type, self.meta)


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------

def clean_name(name, max_len=config.NAME_MAX_LEN):
    """Normalise a display name and refuse anything that can break a header."""
    if not isinstance(name, str):
        raise ProtocolError("name must be text")
    name = name.strip()
    name = name.replace("|", "_")
    name = "".join(ch for ch in name if ch.isprintable()).strip()
    if not name:
        raise ProtocolError("empty name")
    return name[:max_len]


def encode_hi(name, tcp_port, purpose=PURPOSE_CHAT):
    name = clean_name(name)
    if not 0 < int(tcp_port) < 65536:
        raise ProtocolError("invalid TCP port")
    if purpose not in PURPOSES:
        raise ProtocolError("invalid connection purpose %r" % purpose)
    return ("%s|%s|%d|%s|" % (
        TYPE_HI, name, int(tcp_port), purpose)).encode("utf-8")


def encode_msg(text):
    data = text.encode("utf-8", "replace")
    if len(data) > config.MAX_MESSAGE:
        raise ProtocolError("message too long (%d bytes)" % len(data))
    return b"MSG|%d|" % len(data) + data


def encode_file_header(filename, size):
    size = int(size)
    if size < 0:
        raise ProtocolError("negative file size")
    safe = quote(os.path.basename(filename.replace("\\", "/")), safe="")
    if not safe:
        raise ProtocolError("empty file name")
    return ("%s|%s|%d|" % (TYPE_FILE, safe, size)).encode("utf-8")


def encode_bye():
    return b"BYE|"


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

class FrameReader(object):
    """Buffered frame reader for one TCP connection.

    Only one thread may read from a FrameReader (the receiver thread of that
    connection). Sending uses the socket directly and is guarded by the
    connection's own lock.
    """

    def __init__(self, sock, max_header=config.HEADER_MAX):
        self._sock = sock
        self._buf = bytearray()
        self._max_header = max_header

    # -- low level ---------------------------------------------------------
    def _recv_more(self):
        chunk = self._sock.recv(config.RECV_CHUNK)
        if not chunk:
            raise ConnectionClosed("peer closed the connection")
        self._buf.extend(chunk)

    def _index_after_pipes(self, count):
        """Return the offset just after the count-th '|' (or raise)."""
        while True:
            pos = -1
            for _ in range(count):
                pos = self._buf.find(PIPE, pos + 1)
                if pos == -1:
                    break
            if pos != -1:
                return pos + 1
            if len(self._buf) > self._max_header:
                raise ProtocolError("header longer than %d bytes" % self._max_header)
            self._recv_more()

    def _read_header_line(self, pipes):
        end = self._index_after_pipes(pipes)
        line = bytes(self._buf[:end])
        del self._buf[:end]
        return line

    # -- public API --------------------------------------------------------
    def read_header(self):
        """Read one frame header and leave its payload in the buffer."""
        end = self._index_after_pipes(1)
        try:
            ftype = bytes(self._buf[:end - 1]).decode("utf-8")
        except UnicodeDecodeError:
            raise ProtocolError("frame type is not valid UTF-8")

        if ftype == TYPE_HI:
            raw = self._read_header_line(4).decode("utf-8", "replace")
            parts = raw.split("|")          # ['HI', name, port, purpose, '']
            if len(parts) != 5:
                raise ProtocolError("malformed HI header")
            try:
                port = int(parts[2])
            except ValueError:
                raise ProtocolError("malformed HI port")
            if not 0 < port < 65536:
                raise ProtocolError("HI port out of range")
            purpose = parts[3]
            if purpose not in PURPOSES:
                raise ProtocolError("unknown HI purpose %r" % purpose)
            return Header(TYPE_HI, {
                "name": clean_name(parts[1]),
                "port": port,
                "purpose": purpose,
            })

        if ftype == TYPE_MSG:
            raw = self._read_header_line(2).decode("ascii", "replace")
            parts = raw.split("|")          # ['MSG', length, '']
            if len(parts) != 3:
                raise ProtocolError("malformed MSG header")
            try:
                length = int(parts[1])
            except ValueError:
                raise ProtocolError("malformed MSG length")
            if not 0 <= length <= config.MAX_MESSAGE:
                raise ProtocolError("MSG length out of range")
            return Header(TYPE_MSG, {"length": length})

        if ftype == TYPE_FILE:
            raw = self._read_header_line(3).decode("utf-8", "replace")
            parts = raw.split("|")          # ['FILE', quoted name, size, '']
            if len(parts) != 4:
                raise ProtocolError("malformed FILE header")
            name = unquote(parts[1])
            if not name:
                raise ProtocolError("empty FILE name")
            try:
                size = int(parts[2])
            except ValueError:
                raise ProtocolError("malformed FILE size")
            if size < 0:
                raise ProtocolError("negative FILE size")
            return Header(TYPE_FILE, {"name": name, "size": size})

        if ftype == TYPE_BYE:
            self._read_header_line(1)
            return Header(TYPE_BYE)

        raise ProtocolError("unknown frame type %r" % ftype)

    def read_exact(self, size):
        if size < 0:
            raise ProtocolError("negative read size")
        while len(self._buf) < size:
            self._recv_more()
        data = bytes(self._buf[:size])
        del self._buf[:size]
        return data

    def read_text(self, size):
        return self.read_exact(size).decode("utf-8", "replace")

    def iter_payload(self, size, chunk=config.FILE_CHUNK):
        """Yield exactly `size` bytes, without loading the whole file in RAM."""
        remaining = size
        while remaining > 0:
            if not self._buf:
                self._recv_more()
            take = min(remaining, len(self._buf), chunk)
            yield bytes(self._buf[:take])
            del self._buf[:take]
            remaining -= take


def recv_exact(sock, size):
    """Read exactly `size` bytes from a raw socket (helper for tests/tools)."""
    chunks = []
    remaining = size
    while remaining > 0:
        data = sock.recv(min(remaining, config.RECV_CHUNK))
        if not data:
            raise ConnectionClosed("peer closed the connection")
        chunks.append(data)
        remaining -= len(data)
    return b"".join(chunks)
