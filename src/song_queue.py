import discord
from random import randint
from itertools import islice
import threading
from song import Song
from log import globalLog as gLog

class SongQueue():
    """The song queue."""
    # Global cache for song metadata
    # { url: Song }
    global_cache = dict()

    def __init__(self):
        # The song queue.
        # [(url, Song)]
        #
        # `url` is always present in the queue.
        # `Song` is the metadata for the `url` and is not always present.
        #
        # Before an element can be popped from the queue, you have to make sure
        # that `Song` is present. This either has to be done JIT if the song
        # that we want to play has not yet been extracted, or in the background
        # if we are currently playing a song.
        self.songs = list()

        # An event that will be set if there is at least one song available
        self._song_available = threading.Event()

        # Clear the flag as the list is initialized to empty
        self._song_available.clear()

        # (url, Song) pair of the currently playing song.
        # `Song` metadata has to be present at all times.
        self.current_song = None

        # (url, Song) pair of the next song.
        # `Song` metadata may not be present and ALWAYS has to be checked.
        # For example, the `self.shuffle()` function always invalidates
        # the cache.
        self.next_song = None

        # Whether the currently playing song is looping
        self.loop_song = False

        # Whether we choose the next song randomly
        self.shuffle = False

        # The voice channel this queue belongs to
        self.voice = None

        # Threads and thread stuff

        # Indicates whether the next song should be played
        self._start_next_song = threading.Event()

        # Player background thread
        self._player_thread = threading.Thread(target=self._song_player_target)

        # Whether the threads should be stopped.
        # This variable is checked on each loop in the thread and is usually
        # False, unless the queue is deleted or the threads are to be stopped
        # for whatever other reason.
        self._stop_threads = False

        self._player_thread.start()


    def __getitem__(self, item):
        if isinstance(item, slice):
            return list(islice(
                self.songs,
                item.start,
                item.stop,
                item.step)
            )
        else:
            return self.songs[item]


    def __delitem__(self, idx):
        # If the queue will be empty, clear the song availibility flag
        if len(self.songs) == 1:
            self._song_available.clear()
        del self.songs[idx]


    def __iter__(self):
        return self.songs.__iter__()


    def __len__(self):
        return len(self.songs)


    def push(self, url: str, metadata: Song = None):
        """Pushes a (url, Song) pair to the back of the queue"""
        self.songs.append((url, metadata))
        self._song_available.set()


    def next(self, block=False, extract_song=False) -> (str, Song):
        """
        Returns the next queued up ("url", `Song`) pair from the queue.
        If the shuffle flag is set, returns a random pair.
        The pair is removed from the queue.

        If `block` is True, the function blocks until an element can be
        retrieved from the queue (that is, blocks if the queue is empty).
        If set to False, the function returns None if a pair can't be found.

        If `extract_song` is True, this function will make sure that `Song` is
        always present (that is, if the metadata hasn't yet been extracted,
        this function will extract them). If you want to lazily extract metadata
        yourself, set `extract_song` to False. Even if the flag is set to False,
        the metadata may already be cached in.
        """
        # Try to get a valid song in a loop
        song = None
        while song is None:
            # If there isn't a song available and we're not blocking, return.
            # Otherwise wait for a song to appear.
            if not self._song_available.is_set():
                if not block:
                    return None
                self._song_available.wait()

            # Get a song
            idx = 0
            if self.shuffle:
                idx = randint(0, len(self.songs) - 1)
            (url, song) = self.songs.pop(idx)

            # If the queue becomes empty as the result of us popping the song,
            # unset the song availibility flag
            if len(self.songs) == 0:
                self._song_available.clear()

            # If we don't want to extract the metadata, just return what we have
            # found. We don't have to make sure that it is valid.
            if not extract_song:
                return (url, song)

            # Get the song. If the song is invalid, this loop will repeat
            (url, song) = self.extract_song(url)

        # Return what we have found
        return (url, song)


    def invalidate_cache(self, url: str):
        """Invalidates (removes) a song entry from the global cache."""
        SongQueue.global_cache.pop(url, None)


    def extract_song(self, url: str, recache=False) -> (str, Song):
        """
        Extracts a song and returns the (url, Song) pair.
        This function uses the global cache. If you want to recache a song
        (invalidate the old entry), set `recache` to True.

        If the song is invalid (if the metadata doesn't contain a stream),
        returns None.
        """
        song = None

        # If we use the cache, check if we have the song cached already
        if not recache:
            song = SongQueue.global_cache.get(url)

            # If we found the song, return it
            if song is not None:
                return (url, song)

        # Extract the song metadata
        if song is None:
            song = Song(url)

        # Check that we have a valid song
        if song.stream is None:
            return None

        # Cache the result and return it
        SongQueue.global_cache[url] = song
        return (url, song)


    def clear(self):
        """Clears the queue"""
        self._song_available.clear()
        self.songs.clear()


    def pause(self):
        """Pause/Unpause the current song"""
        if self.voice.is_paused():
            self.voice.resume()
        elif self.voice.is_playing():
            self.voice.pause()


    def toggle_song_loop(self):
        """Start/Stop looping the current song"""
        self.loop_song = not self.loop_song


    def toggle_shuffle(self):
        """Turn on/off shuffle mode"""
        self.shuffle = not self.shuffle

        # Invalidate next_song so that we don't cache stale songs
        self.push(self.next_song)
        self.next_song = None


    def skip(self):
        """Skips the currently playing song"""
        # Stop looping the song
        self.loop_song = False

        # Simply stop playing and the background task will queue up a new song
        if self.voice.is_playing():
            self.voice.stop()


    def _song_player_target(self):
        """
        The target function running in the background that plays music in a VC.
        """
        while not self._stop_threads:
            # Clear the next_song event flag
            self._start_next_song.clear()

            # If we're not looping the current song
            if not self.loop_song:
                # If `self.next_song` is None, get a new song while blocking
                if self.next_song is None:
                    self.next_song = self.next(block=True, extract_song=True)

                # Set the current song and also try to get a new song
                self.current_song = self.next_song
                self.next_song    = self.next(block=False, extract_song=False)

            # FFMPEG options to prevent stream closing on lost connections
            before_options  = "-reconnect 1 -reconnect_streamed 1"
            before_options += " -reconnect_delay_max 5"

            # Play the song and when it stops, call `_play_next_song`
            source = discord.FFmpegPCMAudio(
                self.current_song[1].stream,
                before_options=before_options
            )

            # If the bot leaves the channel while playing a song, it throws
            # out an exception and that's about it.
            try:
                self.voice.play(source, after=self._play_next_song)
            except Exception as e:
                gLog.warn(f"While playing: {e}. (Probably left the channel.)")
                break

            # If we're currently looping, don't even dare to delay >:(
            if not self.loop_song:
                # If the there's no next song to play, wait for a new song
                # to become available
                if self.next_song is None:
                    self.next_song = self.next(block=True, extract_song=True)

                # If there is a song available but it hasn't been extracted yet,
                # extract it
                if self.next_song[1] is None:
                    self.next_song = self.extract_song(self.next_song[0])

                # If the song is invalid, wait for a new *valid* song
                if self.next_song is None:
                    self.next_song = self.next(block=True, extract_song=True)

            # At this point `self.next_song` is set to a valid song, so we can
            # safely wait for the current song to finish.
            # Either that or we're looping the current song
            self._start_next_song.wait()


    def _play_next_song(self, error=None):
        """
        Callback to `self.voice.play`. Is called when a song finishes playing.
        Sets the `self._start_next_song` flag so that another song can play
        in `_song_player_target`.
        """
        if error:
            gLog.critical(f"While trying to play next song: {str(error)}")
        self._start_next_song.set()
