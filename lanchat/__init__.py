"""LAN Chat & File Sharing - a small peer-to-peer console application.

Every instance is both a client and a server:
  * UDP 9999          -> presence broadcast + discovery
  * TCP <port>        -> chat messages and file transfers

Run with:  python -m lanchat --name Quan --port 5001
"""

__version__ = "1.0.2"
