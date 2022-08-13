class SongQueue():
    """The song queue."""
    def __init__(self):
        # The song queue
        self.songs = []

        # The voice channel this queue belongs to
        self.voice = None
