import random

import discord
import discord.utils
from discord.ext import tasks, commands
from colorama import Fore
from datetime import datetime
import platform
import asyncio
import datetime
import config
import presets

intents = discord.Intents.all()
intents.typing = True
intents.presences = True
intents.members = True
intents.guilds = True


@tasks.loop(seconds=30)
async def statusLoop():
    await client.wait_until_ready()
    await client.change_presence(status=discord.Status.idle,
                                 activity=discord.Activity(type=discord.ActivityType.watching,
                                                           name=f"{len(client.guilds)} servers. 🧐"))
    await asyncio.sleep(10)
    memberCount = 0
    for guild in client.guilds:
        memberCount += guild.member_count
    await client.change_presence(status=discord.Status.dnd,
                                 activity=discord.Activity(type=discord.ActivityType.listening,
                                                           name=f"{memberCount} people! 😀", ))
    await asyncio.sleep(10)


class Client(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=commands.when_mentioned_or('.'), intents=discord.Intents().all())
        self.cogsList = ["cogs.council", "cogs.info", "cogs.suggest"]

    async def setup_hook(self):
        for ext in self.cogsList:
            await self.load_extension(ext)

    async def on_ready(self):
        print(presets.prefix() + " Logged in as " + Fore.YELLOW + self.user.name)
        print(presets.prefix() + " Bot ID " + Fore.YELLOW + str(self.user.id))
        print(presets.prefix() + " Discord Version " + Fore.YELLOW + discord.__version__)
        print(presets.prefix() + " Python version " + Fore.YELLOW + platform.python_version())
        print(presets.prefix() + " Syncing slash commands...")
        synced = await self.tree.sync()
        print(presets.prefix() + " Slash commands synced " + Fore.YELLOW + str(len(synced)) + " Commands")
        print(presets.prefix() + " Initializing status....")
        if not statusLoop.is_running():
            statusLoop.start()

    async def on_message(self, message):
        await self.check_toxicity(message)
        valid_greetings = {"hi", "hello", "sup", "hi!", "hello!", "sup!", "hello everyone", "hello everyone!"}
        valid_hrus = {"hru?", "hru", "how are you?", "how are you", "how have you been?", "how have you been"}

        now = datetime.datetime.utcnow()
        if message.content.lower() in valid_greetings and now - datetime.timedelta(
                hours=72) <= message.author.joined_at <= now:
            rules_channel = message.guild.rules_channel
            embed = discord.Embed(
                title=f"Hello, {message.author.name}!",
                description=f"Welcome to WWC's Discord, {message.author.mention}! "
                            f"We're glad to have you here. Please take a moment to read our rules in "
                            f"{rules_channel.mention}. "
                            f"If you have any questions, don't hesitate to ask in the appropriate channel. Enjoy your "
                            f"stay!",
                color=0x00ff00
            )
            await message.channel.send(embed=embed)

        elif message.content.lower() in valid_hrus:
            responses = [
                "Thanks! I'm fine! How are you?",
                "Great, thank you. How are you?",
                "Good, thanks, and you?",
                "Fine, thanks. How are you?",
                "I’m doing well.",
                "I’m fine, maybe a little tired. I need some more coffee. ☕",
                "Good, thanks.",
                "Not bad, thanks. How about you?",
                "I'm doing alright. How about you?",
                "Can't complain, thanks. How are you?",
                "I'm doing well, thank you. How about you?",
                "I'm doing great, thanks. How are you?"
            ]
            await message.channel.send(random.choice(responses))

    async def on_raw_reaction_add(self, payload):
        guild = client.get_guild(payload.guild_id)
        member = await guild.fetch_member(payload.user_id)
        channel = await guild.fetch_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        role = discord.utils.get(guild.roles, name="Assembly Leader")

        print(member, message, role, guild)
        if not member.bot and role in member.roles and payload.emoji.name == "🔒":
            current_time = datetime.datetime.now()
            approvals = discord.utils.get(message.reactions, emoji="✅")
            denials = discord.utils.get(message.reactions, emoji="❎")
            count_sum = approvals.count - denials.count
            # self.cursor.execute("UPDATE assembly_suggestions SET votes=%s, updated_at='%s' "
            #                     "WHERE message_id=%s" % (count_sum, current_time, payload.message_id))
            # self.connection.commit()
            embed = discord.Embed(title="Suggestion closed!", color=0xff0000)
            embed.add_field(name="Closed!",
                            value=f"Suggestion #{message.id} has been 🔒 closed by the Assembly Leader {member.mention}",
                            inline=True)
            embed.add_field(name="Voting Result!", value=f"\nVotes result: **{approvals.count}** - **{denials.count}**",
                            inline=True)
            await channel.send(embed=embed)
            await message.clear_reactions()
            await message.add_reaction("🔓")
        elif not member.bot and role in member.roles and payload.emoji.name == "🔓":
            await message.clear_reactions()
            await message.add_reaction('✅')
            await message.add_reaction('❎')
            await message.add_reaction('🔒')
            embed = discord.Embed(title="Suggestion re-opened!", color=0x00ff00)
            embed.add_field(name="Re-Opened!",
                            value=f"Suggestion #{message.id} has been 🔓 re-opened by the Assembly Leader"
                                  f" {member.mention}\nYou can now vote again on this suggestion!")
            await channel.send(embed=embed)


client = Client()

client.run(presets.token)
