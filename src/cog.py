# The Siren music cog. This is the engine of the bot and defines all the
# functions this bot uses.
# The intents required by this bot are:
#     voice_states

import discord
from discord import Option
from discord import ApplicationContext
from discord import WebhookMessage
from discord.ext import commands
from song_queue import SongQueue
from song import get_urls_from_query
from log import globalLog as gLog

class Siren(commands.Cog):
    def __init__(self, bot):
        # The bot this cog is assigned to
        self.bot = bot

        # Queues of the servers this bot is in
        # { guild_id: SongQueue }
        self.queues = {}


    @commands.slash_command(name="join", description="Join a voice channel")
    async def join_vc(self, ctx: ApplicationContext):
        """
        Join a voice channel the author of this command is currently in.
        If the author is not in a voice channel, or the bot can't join it,
        send an error message.
        """
        # Check if we aren't connected to a voice channel already
        # and make sure that the author is in a VC
        (queue, response) = await self.get_server_queue(ctx)
        if queue is not None:
            return

        # Create a new queue
        queue = SongQueue()

        # Try and join the voice channel
        try:
            queue.voice = await ctx.author.voice.channel.connect()
            self.queues[ctx.guild_id] = queue
            await response.edit_original_message(content="Connected!")
            gLog.debug(f"Joined a voice channel in: {ctx.guild.name}")
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
            gLog.debug(f"Left a voice channel in: {ctx.guild.name}")
        except Exception as e:
            await response.edit_original_message(
                    content="Couldn't leave the voice channel.")
            gLog.error(f"Leaving a voice channel in: {ctx.guild.name} -- {e}")


    @commands.slash_command(name="play", description="Play something in a VC",
        query=Option(str, "The query to play", min_length=1, required=True))
    async def play(self, ctx: ApplicationContext, query):
        """Puts a song (or a playlist) into the queue."""
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

        gLog.debug(f"Got a song query: {query}")

        # Get a list of urls to a playlist (if a playlist was given, otherwise
        # just get [single_url]) and append them to the queue
        urls = get_urls_from_query(query)
        for url in urls:
            queue.push(url)

        # Edit the message to reflect our query status.
        query_msg = f"Queued up {len(urls)} song"
        if len(urls) != 1:
            query_msg += "s"

        gLog.debug(f"{query_msg} in {ctx.guild.name}")
        await response.edit_original_message(content=query_msg)


    @commands.slash_command(name="pause", description="Pause/Unpause the current song")
    async def pause(self, ctx: ApplicationContext):
        """Pause the currently playing song."""
        # Get the queue
        (queue, response) = await self.get_server_queue(ctx)
        if not isinstance(queue, SongQueue):
            return

        # Pause the song
        queue.pause()
        await response.edit_original_message(content="Paused!")


    @commands.slash_command(name="clear", description="Clear the queue")
    async def clear_queue(self, ctx: ApplicationContext):
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
        """Skip the currently playing song."""
        # Get the queue
        (queue, response) = await self.get_server_queue(ctx)
        if not isinstance(queue, SongQueue):
            return

        # Skip the song
        queue.skip()
        await response.edit_original_message(content="Skipped!")


    @commands.slash_command(name="shuffle", description="Turn on/off shuffling")
    async def toggle_shuffle_mode(self, ctx: ApplicationContext):
        """Toggle the shuffle mode of a guild's queue"""
        # Get the queue
        (queue, response) = await self.get_server_queue(ctx)
        if not isinstance(queue, SongQueue):
            return

        # Toggle the shuffle mode
        queue.toggle_shuffle()

        # Send a notification about the shuffle status
        msg = "Shuffle disabled."
        if queue.shuffle:
            msg = "Shuffle enabled"
        await response.edit_original_message(content=msg);


    @commands.slash_command(name="loop", description="Turn on/off song looping")
    async def toggle_song_loop_mode(self, ctx: ApplicationContext):
        """Toggle the song loop mode of a guild's queue"""
        # Get the queue
        (queue, response) = await self.get_server_queue(ctx)
        if not isinstance(queue, SongQueue):
            return

        # Toggle the loop mode
        queue.toggle_song_loop()

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
