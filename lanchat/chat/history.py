"""Chat history and unread counters, protected by one lock."""

import threading

from .. import config


class ChatHistory(object):
    def __init__(self, limit=config.HISTORY_LIMIT):
        self._lock = threading.RLock()
        self._messages = {}   # peer name -> list of formatted lines
        self._unread = {}     # peer name -> int
        self._limit = int(limit)

    def add(self, peer, text, author):
        """Store one message and return the new unread counter for that peer."""
        line = "[%s] %s" % (author, text)
        with self._lock:
            bucket = self._messages.setdefault(peer, [])
            bucket.append(line)
            if len(bucket) > self._limit:
                del bucket[:len(bucket) - self._limit]
            unread = self._unread.get(peer, 0) + 1
            self._unread[peer] = unread
            return unread

    def mark_read(self, peer):
        with self._lock:
            self._unread[peer] = 0

    def unread_count(self, peer):
        with self._lock:
            return self._unread.get(peer, 0)

    def messages(self, peer):
        with self._lock:
            return list(self._messages.get(peer, []))

    def clear(self, peer=None):
        with self._lock:
            if peer is None:
                self._messages.clear()
                self._unread.clear()
            else:
                self._messages.pop(peer, None)
                self._unread.pop(peer, None)
