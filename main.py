"""
Councillor Discord Bot - Main Entry Point
A Discord bot for managing democratic processes in Discord communities
"""
import discord
from discord.ext import tasks, commands
import asyncio
import platform
from colorama import Fore
from datetime import datetime

import config
from utils.database import DatabaseHelper, row_to_doc, wrap_list_rows
from utils.helpers import datetime_now, seconds_until
from utils.enums import VotingStatus, VotingType, VOTING_TYPE_CONFIG
from utils.formatting import format_voting_result, create_embed
from utils.errors import handle_command_error
from appwrite.client import Client as AppwriteClient
from appwrite.services.tables_db import TablesDB
from appwrite.query import Query


# ============================================
# Appwrite Setup
# ============================================

appwrite_client = AppwriteClient()
appwrite_client.set_endpoint(config.APPWRITE_ENDPOINT)
appwrite_client.set_project(config.APPWRITE_PROJECT)
appwrite_client.set_key(config.APPWRITE_KEY)

tables_db = TablesDB(appwrite_client)
db_helper = DatabaseHelper(tables_db)


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
        # Activate scheduled elections/proposals that were pending until voting_start
        pending_result = tables_db.list_rows(
            database_id=config.APPWRITE_DB_NAME,
            table_id="votings",
            queries=[Query.equal("status", VotingStatus.PENDING.value)],
        )
        for row in pending_result.rows:
            doc = row_to_doc(row)
            vs = doc.get("voting_start")
            if not vs:
                continue
            try:
                start_dt = datetime.fromisoformat(vs.replace("Z", "+00:00"))
            except ValueError:
                continue
            if start_dt <= current_datetime or config.DEBUG_MODE:
                await db_helper.update_voting(
                    doc["$id"],
                    {"status": VotingStatus.VOTING.value},
                )
                log(f"Activated voting {doc['$id']} (pending → voting)", "INFO")

        # Get all votings that should be finalized.
        # In debug mode, treat every active voting as ended.
        ended_queries = [Query.equal("status", VotingStatus.VOTING.value)]
        if not config.DEBUG_MODE:
            ended_queries.append(Query.less_than_equal("voting_end", current_datetime.isoformat()))

        ended = tables_db.list_rows(
            database_id=config.APPWRITE_DB_NAME,
            table_id="votings",
            queries=ended_queries,
        )
        all_votings = wrap_list_rows(ended)
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
        candidates = await db_helper.get_candidates(voting["$id"])
        if not candidates:
            log(f"No candidates found for election {voting['$id']}", "WARNING")
            await db_helper.update_council(guild.id, {"election_in_progress": False})
            await db_helper.update_voting(
                voting["$id"],
                {"status": VotingStatus.FAILED.value, "result_announced": True},
            )
            return

        candidates.sort(key=lambda x: x.get("vote_count", 0), reverse=True)
        voting_type = VotingType(voting["type"])

        elected: list[dict] = []
        role_synced = False

        if voting_type == VotingType.ELECTION:
            max_councillors = guild_data.get("max_councillors", 9)
            councillor_role = None
            if guild_data.get("councillor_role_id"):
                councillor_role = guild.get_role(int(guild_data["councillor_role_id"]))
                role_synced = councillor_role is not None

            chancellor_role = None
            if guild_data.get("chancellor_role_id"):
                chancellor_role = guild.get_role(int(guild_data["chancellor_role_id"]))

            current_councillors = await db_helper.list_councillors(guild.id, active_only=True)
            for councillor in current_councillors:
                await db_helper.update_councillor(councillor["$id"], {"active": False, "is_chancellor": False})
                member = guild.get_member(int(councillor["discord_id"]))
                if member and councillor_role and councillor_role in member.roles:
                    try:
                        await member.remove_roles(councillor_role, reason="Council term ended")
                    except discord.HTTPException:
                        pass
                if member and chancellor_role and chancellor_role in member.roles:
                    try:
                        await member.remove_roles(chancellor_role, reason="Council term ended")
                    except discord.HTTPException:
                        pass

            for candidate in candidates[:max_councillors]:
                if int(candidate.get("vote_count", 0)) <= 0:
                    continue

                existing = await db_helper.get_councillor(candidate["discord_id"], guild.id)
                if existing:
                    await db_helper.update_councillor(
                        existing["$id"],
                        {"active": True, "is_chancellor": False, "name": candidate["name"]},
                    )
                else:
                    await db_helper.create_councillor(
                        discord_id=candidate["discord_id"],
                        name=candidate["name"],
                        guild_id=guild.id,
                    )

                await db_helper.update_candidate(candidate["$id"], {"elected": True})
                elected.append(candidate)

                member = guild.get_member(int(candidate["discord_id"]))
                if member and councillor_role and councillor_role not in member.roles:
                    try:
                        await member.add_roles(councillor_role, reason="Elected to council")
                    except discord.HTTPException:
                        pass

            await db_helper.update_council(
                guild.id,
                {"election_in_progress": False, "current_chancellor_id": None},
            )

        else:
            # For other election types, keep existing ranking behavior.
            elected = candidates[:1]

        embed = create_embed(
            title="🗳️ Election Results",
            description=f"**{voting['title']}**",
            color=0x00B0F4,
        )

        max_display = min(10, len(candidates))
        for i, candidate in enumerate(candidates[:max_display], 1):
            vote_count = candidate.get("vote_count", 0)
            suffix = " ✅" if candidate in elected else ""
            embed.add_field(
                name=f"{i}. {candidate['name']}{suffix}",
                value=f"Votes: {vote_count}",
                inline=False,
            )

        embed.set_footer(
            text=(
                f"Elected: {len(elected)}"
                + (" • Roles synced" if role_synced else "")
            )
        )

        if guild_data.get("announcement_channel_id"):
            channel = guild.get_channel(int(guild_data["announcement_channel_id"]))
        elif guild_data.get("voting_channel_id"):
            channel = guild.get_channel(int(guild_data["voting_channel_id"]))
        else:
            channel = None

        if channel:
            await channel.send(embed=embed)

        await db_helper.update_voting(
            voting["$id"],
            {"status": VotingStatus.PASSED.value, "result_announced": True},
        )

        log(f"Processed election {voting['$id']} (elected: {len(elected)})", "SUCCESS")

    except Exception as e:
        log(f"Error processing election result: {e}", "ERROR")


@tasks.loop(minutes=30)
async def expire_decrees_loop():
    """Deactivate decrees that have passed their expiry timestamp."""
    try:
        expired = await db_helper.expire_decrees()
        if expired > 0:
            log(f"Expired {expired} decree(s)", "INFO")
    except Exception as e:
        log(f"Error in decree expiry task: {e}", "ERROR")


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
            "cogs.chancellor",
            "cogs.laws",
            "cogs.webserver",
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

        if not expire_decrees_loop.is_running():
            expire_decrees_loop.start()
            log("Started decree expiry task", "SUCCESS")

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
