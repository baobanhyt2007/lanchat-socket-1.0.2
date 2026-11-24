"""File sending and receiving over a dedicated TCP connection.

One file = one connection: connect -> HI -> FILE header + bytes -> close.
This keeps the chat connection free, so chatting never blocks during a
transfer and no MSG frame can ever be inserted inside a FILE payload.
"""

import os
import socket
import threading
from pathlib import Path

from .. import config, protocol
from ..errors import TransferError

_WINDOWS_RESERVED = {
    "con", "prn", "aux", "nul",
    "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9",
    "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9",
}


def safe_filename(name, fallback="received_file"):
    """Turn whatever the peer sent into a safe base name for downloads/."""
    # Replace ':' first: ntpath treats "a:b" as a drive + name and would
    # silently drop "a" instead of showing that the name was sanitised.
    name = (name or "").replace(":", "_").replace("\\", "/")
    name = os.path.basename(name)
    name = "".join(ch for ch in name if ch.isprintable()).strip()
    for char in '<>"/\\|?*':
        name = name.replace(char, "_")
    name = name.strip(". ")
    if not name or name in (".", ".."):
        return fallback
    stem = Path(name).stem.lower()
    if stem in _WINDOWS_RESERVED:
        name = "file_" + name
    if len(name) > 120:
        suffix = Path(name).suffix[:16]
        name = name[:120 - len(suffix)] + suffix
    return name


def unique_path(path):
    """downloads/report.pdf -> downloads/report (1).pdf if it already exists."""
    path = Path(path)

    def taken(candidate):
        return candidate.exists() or Path(str(candidate) + ".part").exists()

    if not taken(path):
        return path
    stem, suffix = path.stem, path.suffix
    for index in range(1, 1000):
        candidate = path.with_name("%s (%d)%s" % (stem, index, suffix))
        if not taken(candidate):
            return candidate
    raise TransferError("too many files with the same name")


class FileService(object):
    """Stateless helper wired to the App through two callbacks."""

    def __init__(self, self_name, self_port, download_dir=config.DOWNLOAD_DIR,
                 on_progress=None, on_notice=None):
        self.self_name = self_name
        self.self_port = int(self_port)
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self._progress = on_progress or (lambda *args: None)
        self._notice = on_notice or (lambda *args: None)

    # -- sending -----------------------------------------------------------
    def send_async(self, path, peer):
        thread = threading.Thread(
            target=self._send, args=(Path(path), peer),
            daemon=True, name="file-tx-%s" % peer.name)
        thread.start()
        return thread

    def _emit_progress(self, direction, name, size, sent, peer_name, state):
        percent = 100 if size <= 0 else min(100, int(sent * 100 / size))
        while state["next"] < len(config.PROGRESS_STEPS):
            step = config.PROGRESS_STEPS[state["next"]]
            if percent < step:
                break
            self._progress(direction, name, step, peer_name)
            state["next"] += 1

    def _send(self, path, peer):
        name = path.name
        try:
            size = path.stat().st_size
        except OSError as exc:
            self._notice("[!] Cannot read %s: %s" % (name, exc))
            return
        self._notice("[*] Sending %s (%.1f KB) to %s ..." % (
            name, size / 1024.0, peer.name))
        sock = None
        state = {"next": 0}
        try:
            sock = socket.create_connection(
                (peer.ip, peer.tcp_port), timeout=config.CONNECT_TIMEOUT)
            sock.sendall(protocol.encode_hi(
                self.self_name, self.self_port, protocol.PURPOSE_FILE))
            sock.sendall(protocol.encode_file_header(name, size))

            sent = 0
            if size == 0:
                self._emit_progress("send", name, 0, 0, peer.name, state)
            else:
                with path.open("rb") as handle:
                    while True:
                        chunk = handle.read(config.FILE_CHUNK)
                        if not chunk:
                            break
                        sock.sendall(chunk)
                        sent += len(chunk)
                        self._emit_progress("send", name, size, sent, peer.name, state)
            self._emit_progress("send", name, max(size, 1), size, peer.name, state)
            self._notice("[*] Sent %s to %s." % (name, peer.name))
        except OSError as exc:
            self._notice("[!] Sending %s to %s failed: %s" % (
                name, peer.name, exc))
        except (protocol.ProtocolError, TransferError) as exc:
            self._notice("[!] Sending %s failed: %s" % (name, exc))
        finally:
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass

    # -- receiving ---------------------------------------------------------
    def receive(self, conn, reader, meta, peer_name, peer_ip=None):
        """Save one incoming FILE frame. Runs in that connection's thread."""
        raw_name = meta.get("name", "")
        size = int(meta.get("size", 0))
        name = safe_filename(raw_name)
        final_path = unique_path(self.download_dir / name)
        temp_path = Path(str(final_path) + ".part")

        self._notice("[*] Receiving %s (%.1f KB) from %s ..." % (
            name, size / 1024.0, peer_name))
        state = {"next": 0}
        received = 0
        try:
            with temp_path.open("wb") as handle:
                for chunk in reader.iter_payload(size):
                    handle.write(chunk)
                    received += len(chunk)
                    self._emit_progress("receive", name, size, received,
                                        peer_name, state)
            if received != size:
                raise TransferError(
                    "expected %d bytes, received %d" % (size, received))
            os.replace(str(temp_path), str(final_path))
            if size == 0:
                self._emit_progress("receive", name, 1, 1, peer_name, state)
            self._emit_progress("receive", name, max(size, 1), size,
                                peer_name, state)
            self._notice("[*] Saved '%s' from %s -> %s" % (
                final_path.name, peer_name, final_path))
        except Exception as exc:
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except OSError:
                pass
            self._notice("[!] Receiving %s from %s failed: %s" % (
                name, peer_name, exc))
            raise
        finally:
            try:
                conn.close()
            except OSError:
                pass
        return final_path
