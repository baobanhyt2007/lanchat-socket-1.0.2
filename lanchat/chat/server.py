"""TCP server: accepts connections, reads HI, then routes the connection.

One handler thread per connection (the assignment allows this and also allows
select/poll; threads make the audio of the demo much easier to follow):

    acceptor thread
        +-- connection #1 thread -> chat receiver for peer A
        +-- connection #2 thread -> file receiver for one file
        +-- connection #3 thread -> chat receiver for peer B
"""

import socket
import threading

from .. import config, protocol
from ..errors import ConnectionClosed, LanChatError, ProtocolError


class ChatServer(threading.Thread):
    def __init__(self, app, tcp_port):
        threading.Thread.__init__(self, daemon=True, name="tcp-acceptor")
        self.app = app
        self.tcp_port = int(tcp_port)
        self._stop_event = threading.Event()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("", self.tcp_port))       # may raise OSError
        self._sock.listen(16)
        self._sock.settimeout(config.ACCEPT_TIMEOUT)

    def stop(self):
        self._stop_event.set()
        try:
            self._sock.close()
        except OSError:
            pass

    def run(self):
        while not self._stop_event.is_set():
            try:
                conn, addr = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            handler = threading.Thread(
                target=self._handle, args=(conn, addr),
                daemon=True, name="tcp-conn-%s" % (addr[0],))
            handler.start()

    # ------------------------------------------------------------------
    def _handle(self, conn, addr):
        conn.settimeout(None)
        reader = protocol.FrameReader(conn)
        peer_name = None
        try:
            header = reader.read_header()
            if header.type != protocol.TYPE_HI:
                raise ProtocolError("first frame must be HI, got %s"
                                    % header.type)
            peer_name = header.meta["name"]
            peer_port = header.meta["port"]
            purpose = header.meta["purpose"]
            self.app.on_peer_seen(peer_name, addr[0], peer_port)

            if purpose == protocol.PURPOSE_FILE:
                file_header = reader.read_header()
                if file_header.type != protocol.TYPE_FILE:
                    raise ProtocolError(
                        "file connection started with %s" % file_header.type)
                self.app.files.receive(
                    conn, reader, file_header.meta, peer_name, addr[0])
            else:
                self.app.session.attach_incoming(
                    conn, reader, peer_name, addr[0], peer_port)
        except ConnectionClosed:
            pass
        except ProtocolError as exc:
            self.app.console.show(
                "[!] Rejected connection from %s: %s" % (addr[0], exc))
        except LanChatError as exc:
            self.app.console.show(
                "[!] Connection from %s failed: %s" % (addr[0], exc))
        except OSError:
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass
