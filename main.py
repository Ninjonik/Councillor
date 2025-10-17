import discord
from discord.ext import commands, tasks
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.query import Query
from datetime import datetime, time, timedelta, timezone
import asyncio
import platform
import config
import utils
import embeds
import views

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

class CouncilBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=commands.when_mentioned_or('!'), intents=intents)
        self.appwrite_client = Client()
        self.appwrite_client.set_endpoint(config.APPWRITE_ENDPOINT)
        self.appwrite_client.set_project(config.APPWRITE_PROJECT)
        self.appwrite_client.set_key(config.APPWRITE_KEY)
        self.db = Databases(self.appwrite_client)
        self.database_id = config.APPWRITE_DB_NAME

    async def setup_hook(self):
        cogs = ['cogs.governance', 'cogs.executive', 'cogs.elections', 'cogs.admin']
        for cog in cogs:
            await self.load_extension(cog)

    async def on_ready(self):
        print(f"Logged in as {self.user.name}")
        print(f"Bot ID: {self.user.id}")
        print(f"Discord Version: {discord.__version__}")
        print(f"Python version: {platform.python_version()}")
        
        synced = await self.tree.sync()
        print(f"Synced {len(synced)} slash commands")
        
        if not self.status_loop.is_running():
            self.status_loop.start()
        if not self.update_votings.is_running():
            self.update_votings.start()

    async def on_guild_join(self, guild: discord.Guild):
        try:
            self.db.create_document(
                database_id=config.APPWRITE_DB_NAME,
                collection_id='guilds',
                document_id=str(guild.id),
                data={}
            )
            print(f"New guild added: {guild.name}")
        except Exception as e:
            print(f"Error adding guild: {e}")

    async def on_guild_remove(self, guild: discord.Guild):
        try:
            self.db.delete_document(
                database_id=config.APPWRITE_DB_NAME,
                collection_id='guilds',
                document_id=str(guild.id)
            )
            print(f"Guild removed: {guild.name}")
        except Exception as e:
            print(f"Error removing guild: {e}")

    @tasks.loop(hours=24)
    async def update_votings(self):
        if not config.DEBUG_MODE:
            wait = self.seconds_until(0, 5)
            await asyncio.sleep(wait)

        current_datetime = utils.datetime_now()

        for guild in self.guilds:
            try:
                votings_result = self.db.list_documents(
                    database_id=config.APPWRITE_DB_NAME,
                    collection_id='votings',
                    queries=[
                        Query.equal('status', 'voting'),
                        Query.equal('council', str(guild.id) + "_c"),
                        Query.less_than_equal("voting_end", current_datetime.isoformat())
                    ]
                )
                
                votings = votings_result["documents"]
                guild_data = utils.get_guild_data(self.db, guild.id)

                if not guild_data or not guild_data.get("voting_channel_id"):
                    continue
                    
                channel = guild.get_channel(int(guild_data["voting_channel_id"]))
                
                for voting in votings:
                    await self.process_voting_result(voting, guild, channel)

            except Exception as e:
                print(f"Error processing votings for guild {guild.id}: {e}")

    async def process_voting_result(self, voting, guild, channel):
        voting_type_data = utils.voting_types.get(voting["type"])
        if not voting_type_data:
            return

        votes_result = self.db.list_documents(
            database_id=config.APPWRITE_DB_NAME,
            collection_id='votes',
            queries=[Query.equal('voting', voting["$id"])]
        )
        
        votes = votes_result["documents"]
        positive_votes = sum(1 for v in votes if v["stance"])
        negative_votes = len(votes) - positive_votes

        required_percentage = voting_type_data["required_percentage"]
        passed = len(votes) > 0 and (positive_votes / len(votes)) > required_percentage

        proposer_name = None
        if voting.get('proposer'):
            try:
                councillor = self.db.get_document(
                    database_id=config.APPWRITE_DB_NAME,
                    collection_id='councillors',
                    document_id=voting['proposer']
                )
                proposer_name = councillor['name']
            except:
                pass

        embed = embeds.create_voting_result_embed(
            voting["title"],
            voting.get("description", ""),
            passed,
            positive_votes,
            negative_votes,
            required_percentage,
            proposer_name
        )

        if channel:
            await channel.send(embed=embed)
        
        self.db.update_document(
            database_id=config.APPWRITE_DB_NAME,
            collection_id="votings",
            document_id=voting['$id'],
            data={"status": "passed" if passed else "failed"}
        )

    @tasks.loop(seconds=30)
    async def status_loop(self):
        await self.wait_until_ready()
        
        await self.change_presence(
            status=discord.Status.idle,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{len(self.guilds)} servers"
            )
        )
        await asyncio.sleep(10)
        
        member_count = sum(guild.member_count for guild in self.guilds)
        await self.change_presence(
            status=discord.Status.dnd,
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name=f"{member_count} people"
            )
        )
        await asyncio.sleep(10)

    @staticmethod
    def seconds_until(hours: int, minutes: int) -> float:
        target_time = time(hours, minutes)
        now = datetime.now(timezone.utc)
        future_exec = datetime.combine(now.date(), target_time, tzinfo=timezone.utc)
        
        if future_exec <= now:
            future_exec += timedelta(days=1)
        
        return (future_exec - now).total_seconds()

def main():
    bot = CouncilBot()
    bot.run(config.DISCORD_TOKEN)

if __name__ == "__main__":
    main()
