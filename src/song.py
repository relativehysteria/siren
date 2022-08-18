from math import ceil
import yt_dlp
from yt_dlp import YoutubeDL
from log import globalLog as gLog

class Song:
    """Representation of a single song"""
    def __init__(self, url: str):
        """
        Extract information from a direct link to a song that can be
        extracted by yt-dlp.
        An example url is 'https://www.youtube.com/watch?v=3cKtSlsYVEU'.
        """
        # Streams are parsed at the end.
        self.stream = None

        if url is None:
            return

        ytdl_result = get_metadata_from_url(url)

        self.title = ytdl_result.get("title")
        gLog.debug(f"Title: {self.title}")

        self.uploader = ytdl_result.get("uploader")
        gLog.debug(f"Uploader: {self.uploader}")

        self.uploader_url = ytdl_result.get("uploader_url")
        gLog.debug(f"Uploader URL: {self.uploader_url}")

        self.url = ytdl_result.get("webpage_url")
        gLog.debug(f"URL: {self.url}")

        self.duration = ytdl_result.get("duration")
        gLog.debug(f"Duration: {self.duration}")

        self.thumbnail = ytdl_result.get("thumbnail")
        gLog.debug(f"Thumbnail URL: {self.thumbnail}")

        self.duration_formatted = parse_duration(self.duration)
        gLog.debug(f"Formatted duration: {self.duration_formatted}")

        # Get the first stream url that we find
        formats = ytdl_result.get('formats')

        if formats is None:
            return

        for f in formats:
            if f['acodec'].lower() == "none":
                continue
            self.stream = f.get("url")
            gLog.debug(f"Stream URL: {self.stream}")
            return


    def __str__(self) -> str:
        # The string that we will return
        string = ""

        # Get the duration
        if self.duration_formatted:
            string += f"`[{self.duration_formatted}]` "

        # Get the title if we can, otherwise make it "Untitled".
        # If we got a webpage_url, refer the to it
        if self.title:
            if self.url:
                string += f"[{self.title}]({self.url})"
            else:
                string += f"{self.title}"
        else:
            string += "[Untitled]"

        # Return the string
        return string


def get_metadata_from_url(url) -> dict:
    """Get the youtube-dl metadata from a given url."""
    # Strip the url
    url = url.strip()

    # Don't parse DASH manifests and don't download whole playlists if
    # a playlist index was given.
    ydl_opts = {
        'youtube_include_dash_manifest': False,
        'noplaylist': True,
        'quiet': True,
    }

    # Try and get the metadata
    with YoutubeDL(ydl_opts) as ytdl:
        try:
            result = ytdl.extract_info(url, download=False)
        except yt_dlp.DownloadError as e:
            gLog.error(f"While downloading song info: {e}...")
            return dict()

    # If we got a list, convert it to a dictionary
    if isinstance(result, list):
        if len(result) == 0:
            # Invalid song
            return dict()
        result = result[0]

    # Return the metadata
    return result


def parse_duration(duration: int) -> str:
    """Parses the duration in seconds into a readable string"""
    if duration is None:
        return

    duration = ceil(duration)
    minutes, seconds = divmod(duration, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)

    duration = ""
    if days > 0:
        duration += f"{days:02}:"
    if hours > 0 or days > 0:
        duration += f"{hours:02}:"
    duration += f"{minutes:02}:"
    duration += f"{seconds:02}"

    return duration

def get_urls_from_query(query: str) -> [str]:
    """Returns a list of urls parsed from a query.

    Does nothing for a single-song query, but it *should* return a list of urls
    (*not* stream urls) for playlists and such.
    """
    # Strip the query
    query = query.strip()

    # If we don't get a link, we got a simple query, so default to looking it up
    # on youtube
    if not query.startswith("http"):
        query = "ytsearch:" + query

    # Do not extract metadata, only list songs. Quietly.
    ydl_opts = {
        "extract_flat": True,
        "quiet": True,
    }
    with YoutubeDL(ydl_opts) as ytdl:
        result = ytdl.extract_info(query, download=False)

    # # The following debug message is extremely verbose. And is most likely
    # # not needed.
    # gLog.debug(f"Extraction result: {result}")

    # We got a direct url to a single song
    if 'entries' not in result:
        return [query]

    # We got multiple song urls
    urls  = []
    for entry in result['entries']:
        url = entry.get('url')
        if url is None:
            continue
        urls.append(url)

    gLog.debug(f"Parsed urls: {urls}")
    return urls
