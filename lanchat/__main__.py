"""Command-line entry point:  python -m lanchat --name Quan --port 5001"""

import argparse
import os
import socket
import sys

if __package__ in (None, ""):
    # Allow both `python -m lanchat` and `python lanchat/__main__.py`:
    # running the file directly leaves __package__ empty, so point it at the
    # package and put the project root on sys.path before relative imports.
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    __package__ = "lanchat"

from . import __version__, config
from .app import App
from .errors import LanChatError, ProtocolError
from .protocol import clean_name


def bootstrap_console():
    """Enable ANSI escape codes / UTF-8 on the Windows console."""
    if os.name == "nt":
        os.system("")  # switches the console to VT100 mode
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def build_parser():
    parser = argparse.ArgumentParser(
        prog="python -m lanchat",
        description="LAN Chat & File Sharing - UDP discovery + TCP chat/files",
        epilog="Example: python -m lanchat --name Quan --port 5001",
    )
    parser.add_argument(
        "--name", default=socket.gethostname().split(".")[0],
        help="name shown to other peers (default: hostname)")
    parser.add_argument(
        "--port", type=int, default=config.DEFAULT_TCP_PORT,
        help="TCP port for chat and files (default: %(default)s)")
    parser.add_argument(
        "--udp-port", type=int, default=config.UDP_DISCOVERY_PORT,
        help="UDP discovery port (default: %(default)s)")
    parser.add_argument(
        "--bcast", action="append", metavar="ADDR",
        help="broadcast address(es); repeat for several, "
             "e.g. --bcast 255.255.255.255 --bcast 127.255.255.255")
    parser.add_argument(
        "--downloads", default=str(config.DOWNLOAD_DIR),
        help="folder that receives files (default: %(default)s)")
    parser.add_argument(
        "--status", choices=("online", "away"), default="online",
        help="initial presence status (default: %(default)s)")
    parser.add_argument(
        "--version", action="version", version="%(prog)s " + __version__)
    return parser


def main(argv=None):
    bootstrap_console()
    args = build_parser().parse_args(argv)

    try:
        name = clean_name(args.name)
    except ProtocolError as exc:
        print("[!] Invalid --name: %s" % exc, file=sys.stderr)
        return 2
    if not 0 < args.port < 65536:
        print("[!] --port must be between 1 and 65535", file=sys.stderr)
        return 2
    if not 0 < args.udp_port < 65536:
        print("[!] --udp-port must be between 1 and 65535", file=sys.stderr)
        return 2

    app = None
    try:
        app = App(
            name=name,
            tcp_port=args.port,
            udp_port=args.udp_port,
            broadcast_addrs=args.bcast or [config.DEFAULT_BROADCAST],
            download_dir=args.downloads,
            status=args.status,
        )
        app.start()
    except KeyboardInterrupt:
        pass
    except OSError as exc:
        print("[!] Cannot start: %s" % exc, file=sys.stderr)
        print("    TCP port %d may already be in use. Try --port %d."
              % (args.port, args.port + 1), file=sys.stderr)
        return 1
    except LanChatError as exc:
        print("[!] %s" % exc, file=sys.stderr)
        return 1
    finally:
        if app is not None:
            app.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
