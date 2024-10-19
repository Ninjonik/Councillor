import discord
import discord.utils
from appwrite.query import Query
from appwrite.services.databases import Databases
from appwrite.id import ID
from discord.ext import tasks, commands
from colorama import Fore
from datetime import datetime
import platform
import asyncio
import datetime
import config
import presets
from presets import print

intents = discord.Intents.all()
intents.typing = True
intents.presences = True
intents.members = True
intents.guilds = True


def seconds_until(hours, minutes):
    given_time = datetime.time(hours, minutes)
    given_time.replace(tzinfo=datetime.timezone.utc)
    now = presets.datetime_now()
    future_exec = datetime.datetime.combine(now, given_time)
    if (future_exec - now).days < 0:  # If we are past the execution, it will take place tomorrow
        future_exec = datetime.datetime.combine(now + datetime.timedelta(days=1), given_time)  # days always >= 0

    return (future_exec - now).total_seconds()


@tasks.loop(hours=24)
async def update_votings():
    if not config.DEBUG_MODE:
        wait = seconds_until(00, 5)
        print("😉 See ya in ", wait)
        await asyncio.sleep(wait)

    current_datetime = presets.datetime_now()
    print(current_datetime.isoformat())

    a = presets.databases.list_documents(
        database_id=config.APPWRITE_DB_NAME,
        collection_id='votings',
        queries=[
        ]
    )

    for guild in client.guilds:
        votings = presets.databases.list_documents(
            database_id=config.APPWRITE_DB_NAME,
            collection_id='votings',
            queries=[
                Query.equal('council', str(guild.id) + "_c"),
                Query.equal('status', 'voting'),
                Query.less_than_equal("voting_end", current_datetime.isoformat()),
            ]
        )

        votings = votings["documents"]
        print(f"Votings for {guild.id}: {len(votings)}, {votings}")

        guild_data = await presets.get_guild_data(guild.id)

        channel = None

        if guild_data["voting_channel_id"]:
            channel = guild.get_channel(int(guild_data["voting_channel_id"]))

        for voting in votings:
            print("VOTE: ", voting["title"])
            print("CURRENT TIME: ", presets.datetime_now().time())
            print("CURRENT DATE: ", presets.datetime_now().date())
            print("DB VOTING END: ", voting["voting_end"])

            voting_type_data = presets.voting_types[voting["type"]]
            color = discord.Colour(int(voting_type_data["color"], 16))

            # If vote type is a legislation/amendment/decree/something that is being voted on regularly
            if voting["type"] in presets.voting_types and voting["status"] == "voting":
                required_percentage = voting_type_data["required_percentage"]
                text = "**NOT PASSED**."
                color = 0xFF0000
                total_votes = len(voting["votes"])
                positive_votes = 0
                negative_votes = 0
                passed = False
                for councillor_vote in voting["votes"]:
                    if councillor_vote["stance"]:
                        positive_votes += 1
                    else:
                        negative_votes += 1
                if total_votes > 0 and (positive_votes / total_votes) > required_percentage:
                    passed = True
                    color = 0x00FF00
                    text = "**PASSED**."

                if guild_data["voting_channel_id"]:
                    # Send a law voting result informational embed
                    embed = discord.Embed(title=voting["title"], description=voting["description"], color=color)
                    embed.add_field(name="Result:", value=text, inline=False)
                    embed.add_field(name="Voting results:", value=f"For: {positive_votes} | Against: {negative_votes}"
                                                                  f" - >{required_percentage * 100}% "
                                                                  f"required to pass",
                                    inline=False)
                    if voting['proposer']:
                        embed.set_footer(text=f"Originally proposed by: {voting['proposer']['name']}")
                    if channel:
                        await channel.send(embed=embed)

                # Clean up
                presets.databases.update_document(
                    database_id=config.APPWRITE_DB_NAME,
                    collection_id="votings",
                    document_id=voting['$id'],
                    data={
                        "status": "passed" if passed else "failed",
                    }
                )

    print("😉 See ya in exactly 24 hours from now!")


@tasks.loop(seconds=30)
async def status_loop():
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
        self.cogsList = ["cogs.council", "cogs.info", "cogs.propose", "cogs.manage"]

    async def setup_hook(self):
        for ext in self.cogsList:
            await self.load_extension(ext)

    async def on_ready(self):
        print("Logged in as " + Fore.YELLOW + self.user.name)
        print("Bot ID " + Fore.YELLOW + str(self.user.id))
        print("Discord Version " + Fore.YELLOW + discord.__version__)
        print("Python version " + Fore.YELLOW + platform.python_version())
        print("Syncing slash commands...")
        synced = await self.tree.sync()
        print("Slash commands synced " + Fore.YELLOW + str(len(synced)) + " Commands")
        print("Initializing status....")
        if not status_loop.is_running():
            status_loop.start()
        if not update_votings.is_running():
            update_votings.start()

    def on_guild_join(self, guild):
        # Add guild to the database
        stringified_guild_id = str(guild.id)
        presets.databases.create_document(
            database_id=config.APPWRITE_DB_NAME,
            collection_id='guilds',
            document_id=stringified_guild_id,
            data={
                'guild_id': stringified_guild_id,
                'name': guild.name,
                'description': guild.description,
                'council': {
                    '$id': f"{stringified_guild_id}_c",
                    'councillors': []
                }
            }
        )
        print(f"New guild added - {guild.name}")

    def on_guild_update(self, before, after):
        presets.databases.update_document(
            database_id=config.APPWRITE_DB_NAME,
            collection_id='guilds',
            document_id=str(before.id),
            data={
                'name': after.name,
                'description': after.description
            }
        )

    def on_guild_remove(self, guild):
        presets.databases.delete_document(
            database_id=config.APPWRITE_DB_NAME,
            collection_id='guilds',
            document_id=str(guild.id),
        )


client = Client()
client.run(presets.token)
