# The Siren music cog. This is the engine of the bot and defines all the
# functions this bot uses.
# The intents required by this bot are:
#     voice_states

from os import sched_getaffinity
import discord
from discord import Option
from discord import ApplicationContext
from discord import WebhookMessage
from discord import Interaction
from discord import Embed
from discord.ext import commands
from song_queue import SongQueue
from song import get_urls_from_query
from song import Song
from song_cache import SongCache
from log import globalLog as gLog

class Siren(commands.Cog):
    def __init__(self, bot, caching_processes: int = 0):
        """Initialize the cog.

        `bot` is the bot this cog is initialized in.
        `caching_processes` is the amount of subprocesses caching and extracting
        the song metadata in the background. If this less than 1, uses the value
        returned by `len(os.sched_getaffinity(0))`
        """
        # The bot this cog is assigned to
        self.bot = bot

        # Queues of the servers this bot is in
        # { guild_id: SongQueue }
        self.queues = {}

        # Inner song metadata cache
        if caching_processes < 1:
            caching_processes = len(sched_getaffinity(0))
        self.song_cache = SongCache(pool_size=caching_processes)

        gLog.debug("Siren cog initialized.")


    @commands.slash_command(name="join", description="Join a voice channel")
    async def join_vc(self, ctx: ApplicationContext):
        """
        Join a voice channel the author of this command is currently in.
        If the author is not in a voice channel, or the bot can't join it,
        send an error message.
        """
        gLog.debug(f"Got `/join`: {ctx.guild.name} >> {ctx.author}")

        # Check if we aren't connected to a voice channel already
        # and make sure that the author is in a VC
        (queue, response) = await self.get_server_queue(ctx)
        if queue is not None:
            return

        # Create a new queue
        queue = SongQueue(song_cache=self.song_cache)

        # Try and join the voice channel
        try:
            queue.voice = await ctx.author.voice.channel.connect()
            self.queues[ctx.guild_id] = queue
            await response.edit_original_message(content="Connected!")
            gLog.info(f"Joined a voice channel in: {ctx.guild.name}")
        except Exception as e:
            await response.edit_original_message(
                    content="Couldn't join the voice channel.")
            gLog.error(f"Joining a voice channel in: {ctx.guild.name} -- {e}")


    @commands.slash_command(name="leave", description="Leave the voice channel")
    async def leave_vc(self, ctx: ApplicationContext):
        """
        Leave a voice channel if the bot is currently connected to one.
        If the author of the message is not in the same channel,
        the bot won't leave.
        """
        gLog.debug(f"Got `/leave`: {ctx.guild.name} >> {ctx.author}")

        # Get the queue for this guild and make sure we are connected to the
        # same VC as the author
        (queue, response) = await self.get_server_queue(ctx)
        if not isinstance(queue, SongQueue):
            return

        # Try and leave the voice channel
        try:
            await queue.voice.disconnect()
            self.queues.pop(ctx.guild_id)
            await response.edit_original_message(content="Disconnected!")
            gLog.info(f"Left a voice channel in: {ctx.guild.name}")
        except Exception as e:
            await response.edit_original_message(
                    content="Couldn't leave the voice channel.")
            gLog.error(f"Leaving a voice channel in: {ctx.guild.name} -- {e}")


    @commands.slash_command(name="play", description="Play something in a VC",
        query=Option(str, "The query to play", min_length=1, required=True))
    async def play(self, ctx: ApplicationContext, query):
        """Puts a song (or a playlist) into the queue."""
        gLog.debug(f"Got `/play`: {ctx.guild.name} >> {ctx.author}")

        # Get the queue for this guild and make sure we are connected to the
        # same VC as the author
        (queue, response) = await self.get_server_queue(ctx)
        if not isinstance(queue, SongQueue):
            return

        # If the query is empty, bail out
        if not query:
            await response.edit_original_message(content="The query is empty.")
            return

        # Edit the message to reflect our query status
        await response.edit_original_message(content="Querying...")

        gLog.info(f"Got a song query: {query}")

        # Get a list of urls to a playlist (if a playlist was given, otherwise
        # just get [single_url]) and append them to the queue
        urls = get_urls_from_query(query)
        queue += urls

        # Edit the message to reflect our query status.
        query_msg = f"Queued up {len(urls)} song"
        if len(urls) != 1:
            query_msg += "s"

        gLog.debug(f"{query_msg} in {ctx.guild.name}")
        await response.edit_original_message(content=query_msg)


    @commands.slash_command(name="pause", description="Pause/Unpause the current song")
    async def pause(self, ctx: ApplicationContext):
        """Pause the currently playing song."""
        gLog.debug(f"Got `/pause`: {ctx.guild.name} >> {ctx.author}")

        # Get the queue
        (queue, response) = await self.get_server_queue(ctx)
        if not isinstance(queue, SongQueue):
            return

        # Pause the song
        queue.pause()
        await response.edit_original_message(content="Paused!")


    @commands.slash_command(name="clear", description="Clear the queue")
    async def clear_queue(self, ctx: ApplicationContext):
        gLog.debug(f"Got `/clear`: {ctx.guild.name} >> {ctx.author}")

        # Get the queue
        (queue, response) = await self.get_server_queue(ctx)
        if not isinstance(queue, SongQueue):
            return

        # Clear the queue and stop the currently playing song
        queue.clear()
        queue.skip()
        await response.edit_original_message(content="Queue cleared!")


    @commands.slash_command(name="skip", description="Skip the current song")
    async def skip_current_song(self, ctx: ApplicationContext):
        gLog.debug(f"Got `/skip`: {ctx.guild.name} >> {ctx.author}")

        """Skip the currently playing song."""
        # Get the queue
        (queue, response) = await self.get_server_queue(ctx)
        if not isinstance(queue, SongQueue):
            return

        # Skip the song
        queue.skip()
        await response.edit_original_message(content="Skipped!")


    @commands.slash_command(name="current", description="Shows the currently playing song")
    async def show_current(self, ctx: ApplicationContext):
        """Create and send an embed for the currently playing song."""
        gLog.debug(f"Got `/current`: {ctx.guild.name} >> {ctx.author}")

        # Get the queue
        (queue, response) = await self.get_server_queue(ctx)
        if not isinstance(queue, SongQueue):
            return

        # Get the currently playing song
        current_song = queue.current_song
        if current_song is None:
            gLog.debug("No song currently playing.")
            await response.edit_original_message(content="No song is currently playing")
            return

        # Create the embed and send it
        embed = create_song_embed(current_song)
        await response.edit_original_message(embed=embed)


    @commands.slash_command(name="shuffle", description="Turn on/off shuffling")
    async def toggle_shuffle_mode(self, ctx: ApplicationContext):
        """Toggle the shuffle mode of a guild's queue"""
        gLog.debug(f"Got `/shuffle`: {ctx.guild.name} >> {ctx.author}")

        # Get the queue
        (queue, response) = await self.get_server_queue(ctx)
        if not isinstance(queue, SongQueue):
            return

        # Toggle the shuffle mode
        queue.toggle_shuffle()

        gLog.debug(f"Shuffle in: {ctx.guild.name} >> {queue.shuffle}")

        # Send a notification about the shuffle status
        msg = "Shuffle disabled."
        if queue.shuffle:
            msg = "Shuffle enabled"
        await response.edit_original_message(content=msg);


    @commands.slash_command(name="loop", description="Turn on/off song looping")
    async def toggle_song_loop_mode(self, ctx: ApplicationContext):
        """Toggle the song loop mode of a guild's queue"""
        gLog.debug(f"Got `/loop`: {ctx.guild.name} >> {ctx.author}")

        # Get the queue
        (queue, response) = await self.get_server_queue(ctx)
        if not isinstance(queue, SongQueue):
            return

        # Toggle the loop mode
        queue.toggle_song_loop()

        gLog.debug(f"Loop in: {ctx.guild.name} >> {queue.loop}")

        # Send a notification about the shuffle status
        msg = "Looping disabled."
        if queue.loop_song:
            msg = "Looping enabled"
        await response.edit_original_message(content=msg);


    async def get_server_queue(self, ctx: ApplicationContext) -> (SongQueue, WebhookMessage):
        """
        Returns the queue for a given server and the response that was sent
        to the command. This function ALWAYS responds and returns a reponse
        webhook.
        Also checks if the author is connected to the same channel.

        If the author is not in a VC, queue is `False`.
        Else if the bot is not connected to a VC, queue is `None`.
        Else if the author is not in the same VC as the bot, queue is `False`.
        """
        # Get the author's voice state
        voice = ctx.author.voice

        # Check if the author is connected to a VC
        if voice is None:
            resp = await ctx.respond(content="You are not connected to a VC.")
            return (False, resp)

        # Get the voice channel this bot is connected to
        queue = self.queues.get(ctx.guild_id)

        # If we aren't connected to a voice channel but we do track a queue,
        # we have been kicked from it. Destroy the queue.
        if queue is not None:
            if queue.voice is None or not queue.voice.is_connected():
                del self.queues[ctx.guild_id]
                queue = None

        # Check if we are connected to a voice channel
        if queue is None:
            resp = await ctx.respond(content="I'm not connected to a VC!")
            return (None, resp)

        # Check if we are connected to the same voice channel as the author
        if voice.channel.id != queue.voice.channel.id:
            resp = await ctx.respond(content="You are not present in my VC.")
            return (False, resp)

        # Return the queue
        resp = await ctx.respond(content="I'm connected to a VC!")
        return (queue, resp)


def create_song_embed(song: Song) -> Embed:
    """Creates an embed for a song and returns it"""
    # Make sure that we have a valid song
    if song.stream is None:
        return

    # Extract the data
    query_url = song.url
    channel   = song.uploader
    duration  = song.duration_formatted
    thumbnail = song.thumbnail
    title     = f"{song.title}"

    # If we have a query url, make the title clickable
    if song.url is not None and title != "":
        title = f"[{title}]({query_url})"

    # If we have an uploader url, make the channel clickable
    if song.uploader_url is not None and channel != "":
        channel = f"[{channel}]({song.uploader_url})"

    # Create the embed
    embed = Embed(title="Enqueued", description=title)

    # Add the various information fields
    embed.add_field(name="Duration", value=duration, inline=True)
    embed.add_field(name="Uploader", value=channel, inline=True)
    if thumbnail is not None or thumbnail != "":
        embed.set_thumbnail(url=thumbnail)

    return embed
