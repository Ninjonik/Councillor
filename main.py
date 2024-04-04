import discord
import discord.utils
from appwrite.client import Client
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
    now = datetime.datetime.now()
    future_exec = datetime.datetime.combine(now, given_time)
    if (future_exec - now).days < 0:  # If we are past the execution, it will take place tomorrow
        future_exec = datetime.datetime.combine(now + datetime.timedelta(days=1), given_time)  # days always >= 0

    return (future_exec - now).total_seconds()


@tasks.loop(hours=24)
async def update_votings():
    wait = seconds_until(0, 10)
    print("cya in", wait)
    await asyncio.sleep(wait)
    for guild in client.guilds:
        votes = presets.databases.list_documents(
            database_id=config.APPWRITE_DB_NAME,
            collection_id='votes',
            queries=[
                Query.equal('council', str(guild.id) + "_c")
            ]
        )

        votes = votes["documents"]

        if config.VOTING_CHANNEL_ID:
            channel = guild.get_channel(config.VOTING_CHANNEL_ID)

        law_suggestion_winner = {}
        law_suggestion_most = -1

        for vote in votes:
            db_voting_end = datetime.datetime.fromisoformat(vote['voting_end']).date()
            current_date = datetime.datetime.utcnow().date()

            # tomorrow_date = current_date + datetime.timedelta(days=1) # TODO: for testing purposes
            tomorrow_date = current_date

            # If today's date is the same as the ending db date, then proceed
            if db_voting_end == tomorrow_date:
                if vote["type"] == "law_suggestion":
                    voting_result = 0
                    for councillor_vote in vote["councillor_votes"]:
                        if councillor_vote["stance"]:
                            # Add positive vote
                            voting_result += 1
                        else:
                            # Add negative vote
                            voting_result -= 1
                    # If has more positive votes than previous, set it
                    if voting_result > law_suggestion_most:
                        law_suggestion_winner = vote
                    else:
                        # Remove lost suggested votes from the database
                        presets.databases.delete_document(
                            database_id=config.APPWRITE_DB_NAME,
                            collection_id='votes',
                            document_id=vote["$id"],
                        )

                # If vote type is a law
                if vote["type"] == "law":
                    passed = False
                    color = 0xFF0000
                    text = "**NOT** PASSED."
                    voting_result = 0
                    for councillor_vote in vote["councillor_votes"]:
                        if councillor_vote["stance"]:
                            voting_result += 1
                        else:
                            voting_result -= 1
                    if voting_result > 0:
                        passed = True
                        color = 0x00FF00
                        text = "**PASSED**."

                    if config.VOTING_CHANNEL_ID:
                        # Send a law voting result informational embed
                        embed = discord.Embed(title=vote["title"], description=vote["description"], color=color)
                        embed.add_field(name="Result:", value=text, inline=False)
                        embed.add_field(name="Vote sum:", value=f"**{voting_result}** (1 or more required to pass)",
                                        inline=False)
                        embed.set_footer(text=f"Originally proposed by: {vote['suggester']['name']}")
                        await channel.send(embed=embed)

                    # Clean up - remove already passed / failed law
                    try:
                        presets.databases.delete_document(
                            database_id=config.APPWRITE_DB_NAME,
                            collection_id='votes',
                            document_id=vote["$id"]
                        )
                    except Exception as e:
                        print(e)

        current_date = datetime.datetime.utcnow()
        next_day = current_date + datetime.timedelta(days=1)
        voting_end_date = datetime.datetime(next_day.year, next_day.month, next_day.day, 0, 0, 0)

        if law_suggestion_winner:
            # Send new voting - about the law this time for the vote which had most suggestion votes
            author = guild.get_member(int(law_suggestion_winner["suggester"]["$id"]))
            print(author)

            await presets.createNewVoting(law_suggestion_winner["title"], law_suggestion_winner["description"], author,
                                          guild, voting_end_date, "law")

            # Updating the law_suggestion with most positive votes to the regular voting next day
            presets.databases.delete_document(
                database_id=config.APPWRITE_DB_NAME,
                collection_id='votes',
                document_id=law_suggestion_winner["$id"],
            )

            if not config.VOTING_CHANNEL_ID:
                return

    print("See you in 24 hours from exactly now")


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
        self.cogsList = ["cogs.council", "cogs.info", "cogs.suggest"]

    async def setup_hook(self):
        for ext in self.cogsList:
            await self.load_extension(ext)

    async def on_ready(self):
        print(" Logged in as " + Fore.YELLOW + self.user.name)
        print(" Bot ID " + Fore.YELLOW + str(self.user.id))
        print(" Discord Version " + Fore.YELLOW + discord.__version__)
        print(" Python version " + Fore.YELLOW + platform.python_version())
        print(" Syncing slash commands...")
        synced = await self.tree.sync()
        print(" Slash commands synced " + Fore.YELLOW + str(len(synced)) + " Commands")
        print(" Initializing status....")
        if not status_loop.is_running():
            status_loop.start()
        if not update_votings.is_running():
            update_votings.start()

    async def on_raw_reaction_add(self, payload):
        guild = client.get_guild(payload.guild_id)
        member = await guild.fetch_member(payload.user_id)
        channel = await guild.fetch_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)

        # If not councillor role then you can't do anything c:
        role_id = config.ROLE_COUNCILLOR_ID
        if role_id:
            role = guild.get_role(role_id)
        else:
            print("No councillor role set")
            return

        if member.bot or role not in member.roles:
            print("Member bot / no councillor role")
            return

        voteData = presets.databases.list_documents(
            database_id=config.APPWRITE_DB_NAME,
            collection_id='votes',
            queries=[
                Query.equal('message_id', str(message.id)),
            ]
        )

        if voteData and voteData["documents"] and voteData["documents"][0]:
            voteData = voteData["documents"][0]
        else:
            print("No documents found")
            return

        # Check if past the voting date
        voting_end_date_str = voteData['voting_end'].split('+')[0]  # Remove timezone info
        voting_end_date = datetime.datetime.strptime(voting_end_date_str, "%Y-%m-%dT%H:%M:%S.%f")
        if datetime.datetime.utcnow() > voting_end_date:
            print("Past voting date")
            return

        # Check if vote already exists for this user for this
        councillorVote = presets.databases.list_documents(
            database_id=config.APPWRITE_DB_NAME,
            collection_id='councillor_votes',
            queries=[
                Query.equal('vote', voteData["$id"]),
                Query.equal('councillor', member.id),
            ]
        )

        # Remove the previous vote from DB
        if councillorVote and councillorVote["documents"] and councillorVote["documents"][0]:
            presets.databases.delete_document(
                database_id=config.APPWRITE_DB_NAME,
                collection_id="councillor_votes",
                document_id=councillorVote["documents"][0]["$id"]
            )
            print(f"Removing previous vote from the db for {member.name} in {guild.name}")

        stance = False

        if payload.emoji.name == "✅":
            stance = True

        presets.databases.create_document(
            database_id=config.APPWRITE_DB_NAME,
            collection_id='councillor_votes',
            document_id=ID.unique(),
            data={
                "councillor": str(member.id),
                "vote": voteData["$id"],
                "stance": stance
            }
        )

        print(f"New vote added: {stance} by {member.name} on {voteData['$id']}")

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
