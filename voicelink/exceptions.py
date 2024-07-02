
class VoicelinkException(Exception):
    """Base of all Voicelink exceptions."""


class NodeException(Exception):
    """Base exception for nodes."""


class NodeCreationError(NodeException):
    """There was a problem while creating the node."""


class NodeConnectionFailure(NodeException):
    """There was a problem while connecting to the node."""


class NodeConnectionClosed(NodeException):
    """The node's connection is closed."""
    pass


class NodeNotAvailable(VoicelinkException):
    """The node is currently unavailable."""
    pass


class NoNodesAvailable(VoicelinkException):
    """There are no nodes currently available."""
    pass


class TrackInvalidPosition(VoicelinkException):
    """An invalid position was chosen for a track."""
    pass


class TrackLoadError(VoicelinkException):
    """There was an error while loading a track."""
    pass


class FilterInvalidArgument(VoicelinkException):
    """An invalid argument was passed to a filter."""
    pass

class FilterTagAlreadyInUse(VoicelinkException):
    """A filter with a tag is already in use by another filter"""
    pass

class FilterTagInvalid(VoicelinkException):
    """An invalid tag was passed or Voicelink was unable to find a filter tag"""
    pass

class SpotifyAlbumLoadFailed(VoicelinkException):
    """The voicelink Spotify client was unable to load an album."""
    pass


class SpotifyTrackLoadFailed(VoicelinkException):
    """The voicelink Spotify client was unable to load a track."""
    pass


class SpotifyPlaylistLoadFailed(VoicelinkException):
    """The voicelink Spotify client was unable to load a playlist."""
    pass


class InvalidSpotifyClientAuthorization(VoicelinkException):
    """No Spotify client authorization was provided for track searching."""
    pass


class QueueFull(VoicelinkException):
    pass

class OutofList(VoicelinkException):
    pass

class DuplicateTrack(VoicelinkException):
    pass