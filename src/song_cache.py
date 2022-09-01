from multiprocessing.connection import Connection
from multiprocessing import Manager
from queue import Empty as QueueEmpty
import multiprocessing as mp
from song import Song
from log import globalLog as gLog

class SongCache:
    """
    A cache of { url: Song } pairs that extracts song metadata in background
    processes.

    `pool_size` is the amount of background processes to run. The more servers
    this cache is meant to handle, the higher the pool size should be.
    `pool_size` has to be at least 1.
    Having a `pool_size` too great is likely wasteful and the processes will be
    slowed down by your internet connection anyway. However, if you do have a
    decent internet connection, go wild.

    One process per server should be enough to extract high-priority songs
    (songs that are queued up to be played next) in a timely manner but may not
    be enough to extract and cache other queued up songs.
    """
    def __init__(self, pool_size: int):
        # Check that we have been given a valid pool_size
        if pool_size < 1:
            raise ValueError("pool_size is too low.")

        # The manager for the shared internal `self.cache`
        self.shared_manager = Manager()

        # The internal cache for song metadata
        # { url: Song }
        self.cache = self.shared_manager.dict()

        # A queue of urls. Urls in this queue get cached as soon as possible.
        # This is usually a queue of all the `SongQueue.next_song`s.
        #
        # The elements of the queue are (url, flag). Url is the url string that
        # is to be extracted. The `flag` is a flag (`multiprocessing.Event`)
        # that is to be set when the metadata is extracted.
        self.priority_url_queue = mp.Queue()

        # A queue of urls. If `priority_url_queue` is empty, songs in this queue
        # get cached instead. This is usually a queue of all songs queued up
        # in `SongQueue.songs` that AREN'T `SongQueue.next_song`.
        # That is, songs which have to wait for _at least_ the `current_song`
        # and `next_song` to finish playing.
        self.url_queue = mp.Queue()

        # Whether a song has been put into one of the inner song queues
        self._song_available = mp.Event()
        self._song_available.clear()

        # The pool of background running processes
        self.pool = []
        for i in range(pool_size):
            self.pool.append(mp.Process(
                target=self._wait_for_songs,
                daemon=True,
                name=f"Cache-{i}",
            ))

        # Start the processes.
        for process in self.pool:
            process.start()


    def _wait_for_songs(self):
        """
        The target function of every background running caching process.

        In an infinite loop, it waits for a song to appear in a queue to
        extract its metadata and cache it.
        """
        while True:
            # Try and get a song from the priority queue
            try:
                (url, song_pipe) = self.priority_url_queue.get(block=False)
            except QueueEmpty as e:
                song_pipe = None
                url       = None

            # If we fail, get one from the normal queue
            if url is None:
                try:
                    url = self.url_queue.get(block=False)
                except QueueEmpty as e:
                    pass

            # If we still got nothing, some other process got the url and there
            # are no other urls available. Unset the song available flag and
            # wait for a new one to appear
            if url is None:
                self._song_available.clear()
                self._song_available.wait()
                continue

            gLog.debug(f"Got a url request: {url}")
            gLog.debug(f"Pipe: {song_pipe}")

            # At this point we have the url

            # Check if it isn't cached already
            if url in self.cache:
                gLog.debug(f"Song present in cache")
                if song_pipe is not None:
                    safe_pipe_send(song_pipe, self.cache[url])
                continue

            # Extract the song
            song = Song(url)

            gLog.debug(f"Extracted song: {song}")

            # Cache the song. If it is invalid, cache it as `None`
            if song.stream is None:
                self.cache[url] = None
            else:
                self.cache[url] = song

            # If we're extracting from the priority queue, send the song through
            # the pipe we were given
            if song_pipe is not None:
                safe_pipe_send(song_pipe, song)


    def extract_cache(self, urls: [str]):
        """Extracts and caches songs in the background. The earlier a song is
        in the list, the sooner it will get extracted. However, and although
        the chances are low, some songs may never get extracted if they don't
        get scheduled to get extracted so.

        If you need a single song to be extracted as soon as possible, use
        `prioritized_extract_cache()`.
        """
        gLog.debug(f"Received urls to cache: {urls}")

        # Make sure we get at least one song in a list
        if not isinstance(urls, list) or len(urls) == 0:
            return

        # Put the songs into the queue
        for url in urls:
            self.url_queue.put(url)

        # Set the song availability flag
        self._song_available.set()


    def prioritized_extract_cache(self, url: str, song_pipe: Connection):
        """
        Extracts and caches a single song in the background as soon as possible.
        When the extraction finishes and the song gets cached, it is transmitted
        through the `song_pipe` back to the caller.
        """
        gLog.debug(f"Received url to cache with priority: {url}")

        # Make sure we were given a valid string
        if not isinstance(url, str):
            safe_pipe_send(song_pipe, None)
            return None

        # Pass the pipe and the song to the priority queue
        self.priority_url_queue.put((url, song_pipe))

        # Set the song availability flag
        self._song_available.set()


def safe_pipe_send(pipe: Connection, obj) -> bool:
    """
    A safe wrapper around `pipe.send` that doesn't let any exceptions through.

    If the pipe we send the `obj` through is not corrupted, this function
    returns True, otherwise False.
    """
    try:
        pipe.send(obj)
    except BrokenPipeError as e:
        gLog.debug(f"Got pipe error: {e}")
        return False
