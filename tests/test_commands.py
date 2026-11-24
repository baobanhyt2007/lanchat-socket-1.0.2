"""Tests for the console -> App -> command dispatch wiring.

Regression: Console.run() calls its handler with one argument, but App used to
pass the two-argument handle_line() directly, so every Enter raised
"TypeError: handle_line() missing 1 required positional argument: 'line'".
"""

import socket
import tempfile
import unittest
from pathlib import Path

from lanchat.app import App


def free_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
    finally:
        sock.close()


class AppCommandWiringTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = App("Tester", free_port(), 9999, ["127.0.0.1"],
                       Path(self.tmp.name))

    def tearDown(self):
        self.app.server.stop()
        self.tmp.cleanup()

    def test_dispatch_line_accepts_exactly_one_argument(self):
        # The console calls handler(text); the bound method must not ask for
        # the app again.
        self.app.dispatch_line("/help")
        self.app.dispatch_line("hello with no partner")
        self.app.dispatch_line("")

    def test_start_wires_the_bound_handler_into_the_console(self):
        captured = {}
        self.app.console.run = (
            lambda handler: captured.setdefault("handler", handler))
        self.app.server.start = lambda: None
        self.app.presence.start = lambda: None
        self.app.listener.start = lambda: None

        self.app.start()             # must not raise
        handler = captured["handler"]
        handler("/help")             # would raise TypeError before the fix

    def test_commands_reach_the_app(self):
        calls = []
        self.app.show_peer_list = lambda: calls.append("list")
        self.app.set_status = lambda status: calls.append(("status", status))
        self.app.send_chat_message = lambda text: calls.append(("say", text))

        self.app.dispatch_line("/list")
        self.app.dispatch_line("/status away")
        self.app.dispatch_line("xin chào")

        self.assertEqual(calls, [
            "list", ("status", "away"), ("say", "xin chào")])


if __name__ == "__main__":
    unittest.main()
