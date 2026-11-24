"""Exception hierarchy shared by every module."""


class LanChatError(Exception):
    """Base class for all application errors."""


class ProtocolError(LanChatError):
    """A peer sent a frame we cannot understand."""


class ConnectionClosed(LanChatError):
    """The remote peer closed the socket (recv() returned b"")."""


class PeerOffline(LanChatError):
    """The peer we tried to reach is not available anymore."""


class TransferError(LanChatError):
    """A file transfer could not be completed."""
