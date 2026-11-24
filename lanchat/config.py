"""Central place for every tunable value used by the application."""

import os
from pathlib import Path

# --- networking -----------------------------------------------------------
UDP_DISCOVERY_PORT = 9999
DEFAULT_TCP_PORT = 5001
DEFAULT_BROADCAST = "255.255.255.255"

BROADCAST_INTERVAL = 3.0      # seconds between two HELLO datagrams
PEER_TIMEOUT = 10.0           # a peer is offline after 10 s of silence
SWEEP_INTERVAL = 1.0          # how often the listener checks for timeouts

CONNECT_TIMEOUT = 5.0         # TCP connect() timeout
ACCEPT_TIMEOUT = 0.5          # so the acceptor can notice stop()
UDP_POLL_TIMEOUT = 0.5        # so the listener can notice stop()

RECV_CHUNK = 64 * 1024        # size of a recv() call
FILE_CHUNK = 64 * 1024        # size of a file chunk written to disk
HEADER_MAX = 4096             # refuse absurd headers (protocol abuse)
MAX_MESSAGE = 1024 * 1024     # 1 MiB of UTF-8 text per chat message

PROGRESS_STEPS = (25, 50, 75, 100)
HISTORY_LIMIT = 200           # messages kept per peer in memory

# --- filesystem -----------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DOWNLOAD_DIR = BASE_DIR / "downloads"

# --- names ----------------------------------------------------------------
NAME_MAX_LEN = 32
