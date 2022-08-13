# The Siren music cog. This is the engine of the bot and defines all the
# functions this bot uses.
# The intents required by this bot are:
#     voice_states

import discord
from discord.ext import commands
from song_queue import SongQueue
from log import globalLog as gLog

class Siren(commands.Cog):
    def __init__(self, bot):
        # The bot this cog is assigned to
        self.bot = bot

        # Queues of the servers this bot is in
        # { guild_id: SongQueue }
        self.queues = {}

    @commands.slash_command(name="join", description="Joins a voice channel")
    async def join_vc(self, ctx: discord.ApplicationContext):
        """
        Join a voice channel the author of this command is currently in.
        If the author is not in a voice channel, or the bot can't join it,
        send an error message.
        """
        # Check if we aren't connected to a voice channel already
        if self.queues.get(ctx.guild_id) is not None:
            await ctx.respond(content="I am already connected to a VC.")
            return

        # Get the author's voice state and check if they're connected to a VC
        voice = ctx.author.voice
        if voice is None or voice.channel is None:
            await ctx.respond(content="You are not connected to a VC.")
            return

        # Try and join the voice channel
        try:
            queue = SongQueue()
            queue.voice = await voice.channel.connect()
            self.queues[ctx.guild_id] = queue
            await ctx.respond(content="Connected!")
            gLog.debug(f"Joined a voice channel in: {ctx.guild.name}")
        except Exception as e:
            await ctx.respond(content="Couldn't join the voice channel.")
            gLog.error(f"Joining a voice channel in: {ctx.guild.name} -- {e}");


    @commands.slash_command(name="leave", description="Leaves the voice channel")
    async def leave_vc(self, ctx: discord.ApplicationContext):
        """
        Leave a voice channel if the bot is currently connected to one.
        If the author of the message is not in the same channel,
        the bot won't leave.
        """
        # Get the voice channel this bot is connected to
        queue = self.queues.get(ctx.guild_id)

        # Check if we are connected to a voice channel to begin with
        if queue is None:
            await ctx.respond(content="I am not connected to a VC.")
            return

        # Get the author's voice state and check if they're connected to the VC
        # this bot is connected to
        voice = ctx.author.voice
        if voice is None or voice.channel.id != queue.voice.channel.id:
            await ctx.respond(content="You are not present in my VC.")
            return

        # Try and leave the voice channel
        try:
            await queue.voice.disconnect()
            # TODO: Destroy the queue first
            self.queues.pop(ctx.guild_id)
            await ctx.respond(content="Disconnected!")
            gLog.debug(f"Left a voice channel in: {ctx.guild.name}")
        except Exception as e:
            await ctx.respond(content="Couldn't leave the voice channel.")
            gLog.error(f"Leaving a voice channel in: {ctx.guild.name} -- {e}");
