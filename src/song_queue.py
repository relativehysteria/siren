import multiprocessing as mp
import threading
import discord
from random import randint
from itertools import islice
from song_cache import SongCache
from song import Song
from log import globalLog as gLog

class SongQueue:
    """The song queue and the discord song player.

    Songs are enqueued as urls and cached in the `song_cache`.
    """
    def __init__(self, song_cache: SongCache):
        # The song queue. A list of strings of urls: [ `url`: str ]
        self.songs = list()

        # An event that will be set if there is at least one song available
        self._song_available = threading.Event()
        self._song_available.clear()

        # Extracted song metadata cache
        self.cache = song_cache

        # (url, Song) pair of the currently playing song.
        # `Song` metadata has to be present at all times.
        self.current_song = None

        # Whether the currently playing song is looping
        self.loop_song = False

        # Whether we choose the next song randomly
        self.shuffle = False

        # The voice channel this queue belongs to
        self.voice = None

        # Threads and thread stuff

        # Indicates whether the next song should be played
        self._start_next_song = threading.Event()
        self._start_next_song.clear()

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
        del self.songs[idx]
        if len(self.songs) == 0:
            self._song_available.clear()


    def __iter__(self):
        return self.songs.__iter__()


    def __iadd__(self, value):
        if not isinstance(value, list) and len(value) == 0:
            return
        self.songs += value
        self.cache.extract_cache(value)
        self._song_available.set()


    def __len__(self):
        return len(self.songs)


    def __del__(self):
        self.destroy()


    async def destroy(self):
        """Explicit destructor"""
        gLog.debug("Destructor called.")

        # Stop all threads
        self._stop_threads = True
        gLog.debug("Stopped threads.")

        # Unblock all blocking operations.
        self._song_available.set()
        self._start_next_song.set()
        gLog.debug("Unblocked operations.")

        # Disconnect from the voice channel
        if self.voice is not None and self.voice.is_connected():
            gLog.debug(f"Disconnected from voice {self.voice}.")
            await self.voice.disconnect()


    def push(self, url: str, metadata: Song = None):
        """Pushes a url to the back of the queue"""
        self.songs.append(url)
        self.cache.extract_cache([value])
        self._song_available.set()


    def pop(self, idx: int = -1) -> str:
        """Pops and returns a url from the queue"""
        if len(self.songs) == 1:
            self._song_available.clear()
        return self.songs.pop(idx)


    def next(self, block: bool = False) -> str:
        """
        Returns the next queued up url from the queue.
        If the shuffle flag is set, returns a random url from the queue.
        The url is removed from the queue.

        If `block` is True, will wait for a new url to get queued up if there
        isn't one already. If False, will return None.
        """
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
        url = self.pop(idx)

        # Return the url
        return url


    def clear(self):
        """Clears the queue"""
        # Invalidate the song but don't push it back to the queue
        self.songs.clear()
        self._song_available.clear()


    def pause(self) -> bool:
        """Pause/Unpause the current song and return whether the song is paused
        or not."""
        if self.voice.is_paused():
            self.voice.resume()
            return False
        elif self.voice.is_playing():
            self.voice.pause()
            return True


    def toggle_song_loop(self):
        """Start/Stop looping the current song"""
        self.loop_song = not self.loop_song


    def toggle_shuffle(self):
        """Turn on/off shuffle mode"""
        self.shuffle = not self.shuffle


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
        # Pipe used in `prioritized_extract_cache()`
        (receiver, transmitter) = mp.Pipe()
        transmitter.send(None)

        # Loop for as long as the queue is alive
        while not self._stop_threads:
            gLog.debug(f"Another cycle in player target")

            # If we're not looping the current song
            if not self.loop_song:
                gLog.debug(f"Song is not looping.")

                # Wait for the extraction of the next song to finish
                self.current_song = receiver.recv()
                gLog.debug(f"Received song: {self.current_song}. Caching next.")

                # Try and cache a new song
                next_url = self.next(block=False)
                self.cache.prioritized_extract_cache(next_url, transmitter)

            # If we still don't have a song to play right now
            while self.current_song is None:
                gLog.debug(f"Getting a new song in loop")

                # Wait for the next song to get cached
                self.current_song = receiver.recv()
                gLog.debug(f"Received song: {self.current_song}. Caching next.")

                # Get the next url from the queue.
                # If the current song is still None, block until there is a url
                # for sure.
                if self.current_song is None:
                    next_url = self.next(block=True)
                else:
                    next_url = self.next(block=False)
                gLog.debug(f"Next url in the queue: {next_url}")

                # Cache the next song before we play it
                self.cache.prioritized_extract_cache(next_url, transmitter)

            # FFMPEG options to prevent stream closing on lost connections
            before_options  = "-reconnect 1 -reconnect_streamed 1"
            before_options += " -reconnect_delay_max 5"

            # Play the song and when it stops, call `_play_next_song`
            source = discord.FFmpegPCMAudio(
                self.current_song.stream,
                before_options=before_options
            )

            # If the bot leaves the channel while playing a song, it throws
            # out an exception and that's about it.
            try:
                self.voice.play(source, after=self._play_next_song)
            except Exception as e:
                gLog.warn(f"While playing: {e}. (Probably left the channel.)")
                break

            # Wait for the current song to stop playing
            gLog.debug(f"Waiting for the current song to finish playing.")
            self._start_next_song.wait()
            self._start_next_song.clear()


    def _play_next_song(self, error=None):
        """
        Callback to `self.voice.play`. Is called when a song finishes playing.
        Sets the `self._start_next_song` flag so that another song can play
        in `_song_player_target`.
        """
        if error:
            gLog.critical(f"While trying to play next song: {str(error)}")

        # Signal that we can start playing the next song
        self._start_next_song.set()
