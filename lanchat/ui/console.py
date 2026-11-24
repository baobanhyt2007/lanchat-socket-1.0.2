"""Console UI: one input line at the bottom, everything else above it.

Every thread prints through Console.show(). A single lock protects the screen,
so an incoming message can never be interleaved with the text being typed:

    1. erase the input line     ("\\r" + "\\033[K")
    2. print the new message
    3. redraw "> " + whatever the user had already typed

No third-party library is used (option b of the assignment brief).
"""

import os
import sys
import threading

PROMPT = "> "
CLEAR_LINE = "\r\033[K"

if os.name == "nt":  # pragma: no cover - platform specific
    import msvcrt

    def _get_key():
        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):      # arrow / function keys send 2 codes
            msvcrt.getwch()
            return None
        return ch

    def _setup_terminal():
        return None

    def _restore_terminal(_state):
        pass

else:  # pragma: no cover - platform specific
    import termios
    import tty

    def _get_key():
        ch = sys.stdin.read(1)
        if ch == "\x1b":                # arrow keys: ESC [ A -> ignore
            try:
                sys.stdin.read(2)
            except Exception:
                pass
            return None
        return ch

    def _setup_terminal():
        state = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())
        return state

    def _restore_terminal(state):
        if state is not None:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, state)


class Console(object):
    def __init__(self, prompt=PROMPT):
        self.prompt = prompt
        self._lock = threading.RLock()
        self._buffer = ""
        self._prompt_drawn = False
        self._running = False
        self._restored = False
        self._on_line = None
        self._terminal_state = None

    # -- low level ---------------------------------------------------------
    @staticmethod
    def _write(text):
        try:
            sys.stdout.write(text)
            sys.stdout.flush()
        except (ValueError, OSError):
            pass

    def _draw_prompt(self):
        self._write(self.prompt + self._buffer)
        self._prompt_drawn = True

    # -- API used by every other thread -----------------------------------
    def show(self, line=""):
        """Print one line above the input line and restore the typed text."""
        with self._lock:
            if self._prompt_drawn:
                self._write(CLEAR_LINE)
            self._write("%s\n" % line)
            if self._prompt_drawn and self._running:
                self._draw_prompt()

    def notice(self, line):
        self.show(line)

    def progress(self, line):
        self.show(line)

    # -- main loop ---------------------------------------------------------
    def run(self, on_line):
        """Blocking keyboard loop. `on_line(text)` runs on the main thread."""
        self._on_line = on_line
        self._running = True
        self._terminal_state = _setup_terminal()
        with self._lock:
            self._draw_prompt()
        try:
            while self._running:
                try:
                    ch = _get_key()
                except (KeyboardInterrupt, EOFError):
                    break
                if ch is None:
                    continue

                if ch in ("\r", "\n"):
                    with self._lock:
                        text = self._buffer
                        self._buffer = ""
                        self._write(CLEAR_LINE)
                        self._prompt_drawn = False
                    try:
                        if self._running:
                            self._on_line(text)
                    except Exception as exc:  # a command must never kill the UI
                        self.show("[!] %s: %s" % (type(exc).__name__, exc))
                    with self._lock:
                        if self._running and not self._prompt_drawn:
                            self._draw_prompt()
                elif ch in ("\b", "\x7f"):
                    with self._lock:
                        if self._buffer:
                            self._buffer = self._buffer[:-1]
                            if self._prompt_drawn:
                                self._write("\b \b")
                elif ch == "\x03":              # Ctrl+C
                    break
                elif ch.isprintable():
                    with self._lock:
                        self._buffer += ch
                        if self._prompt_drawn:
                            self._write(ch)
        finally:
            self._running = False
            self._restore_once()

    def stop(self):
        self._running = False
        with self._lock:
            if self._prompt_drawn:
                self._write("\n")
                self._prompt_drawn = False
        self._restore_once()

    def _restore_once(self):
        if self._restored:
            return
        self._restored = True
        _restore_terminal(self._terminal_state)
        self._terminal_state = None
