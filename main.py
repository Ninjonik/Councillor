"""
Councillor Discord Bot - Main Entry Point
A Discord bot for managing democratic processes in Discord communities
"""
import discord
from discord.ext import tasks, commands
import asyncio
import platform
from colorama import Fore
from datetime import datetime, timezone

import config
from utils.database import DatabaseHelper
from utils.helpers import datetime_now, seconds_until
from utils.enums import VotingStatus, VotingType, VOTING_TYPE_CONFIG
from utils.formatting import format_voting_result, format_timestamp, create_embed
from utils.errors import handle_command_error
from appwrite.client import Client as AppwriteClient
from appwrite.services.databases import Databases
from appwrite.query import Query


# ============================================
# Appwrite Setup
# ============================================

appwrite_client = AppwriteClient()
appwrite_client.set_endpoint(config.APPWRITE_ENDPOINT)
appwrite_client.set_project(config.APPWRITE_PROJECT)
appwrite_client.set_key(config.APPWRITE_KEY)

databases = Databases(appwrite_client)
db_helper = DatabaseHelper(databases)


# ============================================
# Discord Bot Setup
# ============================================

intents = discord.Intents.all()
intents.typing = True
intents.presences = True
intents.members = True
intents.guilds = True


def log(message: str, level: str = "INFO"):
    """Enhanced logging with timestamps and colors"""
    timestamp = datetime_now().strftime("%d.%m.%Y %H:%M:%S")
    color_map = {
        "INFO": Fore.WHITE,
        "SUCCESS": Fore.GREEN,
        "WARNING": Fore.YELLOW,
        "ERROR": Fore.RED
    }
    color = color_map.get(level, Fore.WHITE)
    print(f"{Fore.GREEN}{timestamp}{Fore.RESET} {color}[{level}]{Fore.RESET} {message}")


# ============================================
# Background Tasks
# ============================================

@tasks.loop(hours=24)
async def update_votings():
    """Check and update voting statuses daily"""
    if not config.DEBUG_MODE:
        wait = seconds_until(0, 5)  # Run at 00:05 UTC
        log(f"Next voting update in {wait:.0f} seconds", "INFO")
        await asyncio.sleep(wait)

    log("Running voting update task...", "INFO")
    current_datetime = datetime_now()

    try:
        # Get all votings that have ended
        all_votings = databases.list_documents(
            database_id=config.APPWRITE_DB_NAME,
            collection_id='votings',
            queries=[
                Query.equal('status', VotingStatus.VOTING.value),
                Query.less_than_equal("voting_end", current_datetime.isoformat()),
            ]
        )

        votings = all_votings["documents"]
        log(f"Found {len(votings)} votings to process", "INFO")

        for voting in votings:
            await process_voting_result(voting)

        log("Voting update task completed", "SUCCESS")
    except Exception as e:
        log(f"Error in voting update task: {e}", "ERROR")


async def process_voting_result(voting: dict):
    """Process and announce the result of a voting"""
    try:
        # Get the guild
        council_id = voting["council_id"]
        guild_id = council_id.replace("_c", "")
        guild = client.get_guild(int(guild_id))

        if not guild:
            log(f"Guild not found for voting {voting['$id']}", "WARNING")
            return

        guild_data = await db_helper.get_guild(guild_id)
        if not guild_data:
            log(f"Guild data not found for {guild_id}", "WARNING")
            return

        voting_type = VotingType(voting["type"])

        # Handle different voting types
        if voting_type in [VotingType.ELECTION, VotingType.CHANCELLOR_ELECTION]:
            await process_election_result(voting, guild, guild_data)
        else:
            await process_proposal_result(voting, guild, guild_data)

    except Exception as e:
        log(f"Error processing voting {voting.get('$id')}: {e}", "ERROR")


async def process_proposal_result(voting: dict, guild: discord.Guild, guild_data: dict):
    """Process the result of a proposal voting"""
    try:
        # Get all votes
        votes = await db_helper.get_votes_for_voting(voting['$id'])

        total_votes = len(votes)
        yes_votes = sum(1 for v in votes if v.get('stance', False))
        no_votes = total_votes - yes_votes

        required_percentage = voting.get('required_percentage', 0.5)
        passed = False

        if total_votes > 0 and (yes_votes / total_votes) > required_percentage:
            passed = True

        # Get voting type config
        voting_type = VotingType(voting["type"])
        config_data = VOTING_TYPE_CONFIG.get(voting_type, {})

        # Create result embed
        color = 0x00FF00 if passed else 0xFF0000
        embed = create_embed(
            title=voting["title"],
            description=voting.get("description", ""),
            color=color
        )

        result_text = format_voting_result(passed, yes_votes, no_votes, required_percentage)
        embed.add_field(name="Result", value=result_text, inline=False)

        if voting.get('proposer_id'):
            embed.set_footer(text=f"Proposed by councillor {voting['proposer_id']}")

        # Send result to voting channel
        if guild_data.get('voting_channel_id'):
            channel = guild.get_channel(int(guild_data['voting_channel_id']))
            if channel:
                await channel.send(embed=embed)

        # Update voting status
        await db_helper.update_voting(
            voting['$id'],
            {
                'status': VotingStatus.PASSED.value if passed else VotingStatus.FAILED.value,
                'result_announced': True
            }
        )

        log(f"Processed proposal voting {voting['$id']}: {'PASSED' if passed else 'FAILED'}", "SUCCESS")

    except Exception as e:
        log(f"Error processing proposal result: {e}", "ERROR")


async def process_election_result(voting: dict, guild: discord.Guild, guild_data: dict):
    """Process the result of an election"""
    try:
        # Get all candidates and their vote counts
        candidates = await db_helper.get_candidates(voting['$id'])

        if not candidates:
            log(f"No candidates found for election {voting['$id']}", "WARNING")
            return

        # Sort by vote count
        candidates.sort(key=lambda x: x.get('vote_count', 0), reverse=True)

        voting_type = VotingType(voting["type"])

        # Create result embed
        embed = create_embed(
            title="🗳️ Election Results",
            description=f"**{voting['title']}**",
            color=0x00B0F4
        )

        # Add top candidates
        max_display = 10
        for i, candidate in enumerate(candidates[:max_display], 1):
            vote_count = candidate.get('vote_count', 0)
            embed.add_field(
                name=f"{i}. {candidate['name']}",
                value=f"Votes: {vote_count}",
                inline=False
            )

        # Send result
        if guild_data.get('announcement_channel_id'):
            channel = guild.get_channel(int(guild_data['announcement_channel_id']))
        elif guild_data.get('voting_channel_id'):
            channel = guild.get_channel(int(guild_data['voting_channel_id']))
        else:
            channel = None

        if channel:
            await channel.send(embed=embed)

        # Update voting status
        await db_helper.update_voting(
            voting['$id'],
            {
                'status': VotingStatus.PASSED.value,
                'result_announced': True
            }
        )

        log(f"Processed election {voting['$id']}", "SUCCESS")

    except Exception as e:
        log(f"Error processing election result: {e}", "ERROR")


@tasks.loop(seconds=30)
async def status_loop():
    """Update bot status periodically"""
    await client.wait_until_ready()

    # Status 1: Watching servers
    await client.change_presence(
        status=discord.Status.idle,
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{len(client.guilds)} servers"
        )
    )
    await asyncio.sleep(10)

    # Status 2: Listening to members
    member_count = sum(guild.member_count for guild in client.guilds)
    await client.change_presence(
        status=discord.Status.online,
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name=f"{member_count} citizens"
        )
    )
    await asyncio.sleep(10)

    # Status 3: Custom status
    await client.change_presence(
        status=discord.Status.dnd,
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="democracy in action"
        )
    )
    await asyncio.sleep(10)


# ============================================
# Bot Client
# ============================================

class CouncillorBot(commands.Bot):
    """Main bot client"""

    def __init__(self):
        super().__init__(
            command_prefix=commands.when_mentioned_or('.'),
            intents=intents,
            help_command=None  # We'll create a custom help command
        )
        self.db_helper = db_helper
        self.cogs_list = [
            "cogs.council",
            "cogs.info",
            "cogs.propose",
            "cogs.elections",
            "cogs.admin",
            "cogs.chancellor"
        ]

    async def setup_hook(self):
        """Setup hook called when bot is starting"""
        log("Loading cogs...", "INFO")
        for ext in self.cogs_list:
            try:
                await self.load_extension(ext)
                log(f"Loaded {ext}", "SUCCESS")
            except Exception as e:
                log(f"Failed to load {ext}: {e}", "ERROR")

    async def on_ready(self):
        """Called when the bot is ready"""
        log(f"Logged in as {self.user.name}", "SUCCESS")
        log(f"Bot ID: {self.user.id}", "INFO")
        log(f"Discord.py version: {discord.__version__}", "INFO")
        log(f"Python version: {platform.python_version()}", "INFO")

        # Sync slash commands
        log("Syncing slash commands...", "INFO")
        try:
            synced = await self.tree.sync()
            log(f"Synced {len(synced)} commands", "SUCCESS")
        except Exception as e:
            log(f"Failed to sync commands: {e}", "ERROR")

        # Start background tasks
        if not status_loop.is_running():
            status_loop.start()
            log("Started status loop", "SUCCESS")

        if not update_votings.is_running():
            update_votings.start()
            log("Started voting update task", "SUCCESS")

    async def on_guild_join(self, guild: discord.Guild):
        """Called when bot joins a guild"""
        try:
            await db_helper.create_guild(guild.id, guild.name, guild.description or "")
            log(f"Joined new guild: {guild.name} ({guild.id})", "SUCCESS")
        except Exception as e:
            log(f"Error creating guild data for {guild.name}: {e}", "ERROR")

    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        """Called when a guild is updated"""
        try:
            await db_helper.update_guild(
                after.id,
                {
                    'name': after.name,
                    'description': after.description or ""
                }
            )
        except Exception as e:
            log(f"Error updating guild data for {after.name}: {e}", "ERROR")

    async def on_guild_remove(self, guild: discord.Guild):
        """Called when bot is removed from a guild"""
        try:
            await db_helper.delete_guild(guild.id)
            log(f"Left guild: {guild.name} ({guild.id})", "INFO")
        except Exception as e:
            log(f"Error deleting guild data for {guild.name}: {e}", "ERROR")

    async def on_command_error(self, ctx: commands.Context, error: Exception):
        """Global error handler for text commands"""
        await handle_command_error(ctx, error)


# ============================================
# Run Bot
# ============================================

client = CouncillorBot()

if __name__ == "__main__":
    try:
        log("Starting Councillor Bot...", "INFO")
        client.run(config.BOT_TOKEN)
    except KeyboardInterrupt:
        log("Bot stopped by user", "WARNING")
    except Exception as e:
        log(f"Fatal error: {e}", "ERROR")
