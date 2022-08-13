#!/usr/bin/env python
import discord
from log import globalLog as gLog
from cog import Siren

if __name__ != "__main__":
    gLog.debug(f"{__file__} executed but is not __main__")
    exit(0)

# Read the token from the token file
try:
    with open("TOKEN") as f:
        token = f.read().strip()
except Exception as e:
    gLog.critical(f"{e}")
    raise e

# Run the bot
bot = discord.Bot()
bot.add_cog(Siren(bot))

@bot.event
async def on_ready():
    latency = int(bot.latency * 1000)
    gLog.info("READY!")
    gLog.info(f"Startup latency: {latency}ms")

bot.run(token)
