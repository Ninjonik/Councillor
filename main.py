"""
Councillor Discord Bot - Main Entry Point
A Discord bot for managing democratic processes in Discord communities
"""
import json
import discord
from discord.ext import tasks, commands
import asyncio
import platform
from colorama import Fore
from datetime import datetime, timedelta

import config
from cogs.elections import ElectionRegistrationView, ElectionVotingView
from utils.database import DatabaseHelper, row_to_doc, wrap_list_rows
from utils.helpers import datetime_now, seconds_until
from utils.enums import VotingStatus, VotingType, VOTING_TYPE_CONFIG, SettingType, EditableBy
from utils.formatting import format_voting_result, create_embed, format_timestamp
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


AUTOMATION_SCHEDULE_KEYS = {
    VotingType.ELECTION: "auto_council_election_schedule",
    VotingType.CHANCELLOR_ELECTION: "auto_chancellor_election_schedule",
}


async def _find_voting(guild_id: int, voting_type: VotingType, status: VotingStatus) -> dict | None:
    council_id = f"{guild_id}_c"
    result = tables_db.list_rows(
        database_id=config.APPWRITE_DB_NAME,
        table_id="votings",
        queries=[
            Query.equal("council_id", council_id),
            Query.equal("type", voting_type.value),
            Query.equal("status", status.value),
            Query.limit(1),
        ],
    )
    rows = result.rows or []
    if not rows:
        return None
    return {"$id": rows[0].id, **rows[0].data}


async def _latest_voting_end(guild_id: int, voting_type: VotingType) -> datetime | None:
    council_id = f"{guild_id}_c"
    result = tables_db.list_rows(
        database_id=config.APPWRITE_DB_NAME,
        table_id="votings",
        queries=[
            Query.equal("council_id", council_id),
            Query.equal("type", voting_type.value),
            Query.order_desc("voting_end"),
            Query.limit(1),
        ],
    )
    rows = result.rows or []
    if not rows:
        return None
    end_raw = rows[0].data.get("voting_end")
    if not end_raw:
        return None
    try:
        return datetime.fromisoformat(end_raw.replace("Z", "+00:00"))
    except ValueError:
        return None


async def _get_schedule(guild_id: int, key: str) -> dict | None:
    setting = await db_helper.get_setting(key, guild_id)
    if not setting:
        return None
    try:
        value = json.loads(setting.get("value", "{}"))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


async def _set_schedule(guild_id: int, key: str, data: dict) -> None:
    await db_helper.set_setting(
        key=key,
        value=json.dumps(data),
        guild_id=guild_id,
        setting_type=SettingType.JSON,
        description="Internal election automation schedule",
        editable_by=EditableBy.ADMIN,
    )


async def _clear_schedule(guild_id: int, key: str) -> None:
    await _set_schedule(guild_id, key, {})


async def _send_president_notice(guild: discord.Guild, guild_data: dict, voting_type: VotingType, run_date: datetime) -> None:
    role_id = guild_data.get("president_role_id")
    if not role_id:
        return

    role = guild.get_role(int(role_id))
    if not role:
        return

    if voting_type == VotingType.ELECTION:
        title = "Council election automation notice"
        details = (
            f"A council election in **{guild.name}** is scheduled for **{run_date.date().isoformat()} (UTC)**.\n\n"
            "If you want to override channel, @everyone ping, or start/end time, run `/announce_election` before then."
        )
    else:
        title = "Chancellor election automation notice"
        details = (
            f"A chancellor election in **{guild.name}** is scheduled for **{run_date.date().isoformat()} (UTC)**.\n\n"
            "If you want to override channel/time, have a councillor run `/announce_chancellor_election` before then."
        )

    for member in role.members:
        if member.bot:
            continue
        try:
            await member.send(f"**{title}**\n\n{details}")
        except discord.HTTPException:
            continue


async def _auto_announce_election(guild: discord.Guild, guild_data: dict, voting_type: VotingType) -> bool:
    channel_id = guild_data.get("announcement_channel_id") or guild_data.get("voting_channel_id")
    if not channel_id:
        return False

    channel = guild.get_channel(int(channel_id))
    if not isinstance(channel, discord.TextChannel):
        return False

    start_dt = datetime_now() + timedelta(days=1)
    end_dt = start_dt + timedelta(days=1)

    if voting_type == VotingType.ELECTION:
        embed = create_embed(
            title="🗳️ Council Election Announced!",
            description=(
                f"Registration is now open.\n\n"
                f"Voting begins {format_timestamp(start_dt, 'R')}\n"
                f"Voting ends {format_timestamp(end_dt, 'R')}\n\n"
                "Use the buttons below to register as voter or candidate."
            ),
            color=0x00B0F4,
            timestamp=datetime_now(),
        )
        content = None
    else:
        councillors = await db_helper.list_councillors(guild.id, active_only=True)
        if not councillors:
            return False

        embed = create_embed(
            title="👑 Chancellor Election Announced",
            description=(
                "Only active councillors may register and vote.\n\n"
                f"Registration closes {format_timestamp(start_dt, 'R')}\n"
                f"Voting closes {format_timestamp(end_dt, 'R')}"
            ),
            color=0xFFD700,
            timestamp=datetime_now(),
        )
        content = f"<@&{guild_data['councillor_role_id']}>" if guild_data.get("councillor_role_id") else None

    pre_view = ElectionRegistrationView(
        client,
        db_helper,
        "pending",
        voting_type=voting_type,
    )
    message = await channel.send(content=content, embed=embed, view=pre_view)

    title = "Council Election" if voting_type == VotingType.ELECTION else "Chancellor Election"
    description = "Election for new Grand Council members" if voting_type == VotingType.ELECTION else "Election for Chancellor"

    voting = await db_helper.create_voting(
        voting_type=voting_type,
        title=title,
        description=description,
        guild_id=guild.id,
        voting_start=start_dt,
        voting_end=end_dt,
        status=VotingStatus.PENDING,
        message_id=str(message.id),
        required_percentage=0.0,
    )

    if voting_type == VotingType.ELECTION:
        await db_helper.update_council(guild.id, {"election_in_progress": True})

    await message.edit(
        view=ElectionRegistrationView(
            client,
            db_helper,
            voting["$id"],
            voting_type=voting_type,
        )
    )
    return True


async def _auto_start_pending_election(voting: dict, guild: discord.Guild, guild_data: dict) -> bool:
    candidates = await db_helper.get_candidates(voting["$id"])
    voters = await db_helper.get_registered_voters(voting["$id"])
    if not candidates or not voters:
        await db_helper.update_voting(
            voting["$id"],
            {"status": VotingStatus.FAILED.value, "result_announced": True},
        )
        if voting.get("type") == VotingType.ELECTION.value:
            await db_helper.update_council(guild.id, {"election_in_progress": False})
        return False

    channel_id = guild_data.get("voting_channel_id") or guild_data.get("announcement_channel_id")
    if not channel_id:
        return False

    channel = guild.get_channel(int(channel_id))
    if not channel:
        return False

    candidates_text = "\n".join(
        f"{i}. {candidate['name']}"
        for i, candidate in enumerate(candidates[:25], start=1)
    )

    voting_end = datetime.fromisoformat(voting["voting_end"].replace("Z", "+00:00"))
    if voting.get("type") == VotingType.CHANCELLOR_ELECTION.value:
        title = "👑 Chancellor Election - Voting Open"
        color = 0xFFD700
        content = f"<@&{guild_data['councillor_role_id']}>" if guild_data.get("councillor_role_id") else None
        description = (
            f"Only registered councillors may vote.\n\n"
            f"Candidates:\n{candidates_text}\n\n"
            f"Voting closes {format_timestamp(voting_end, 'R')}"
        )
        voting_type = VotingType.CHANCELLOR_ELECTION
    else:
        title = "Council Election - Voting Open"
        color = 0x00FF00
        content = f"<@&{guild_data['citizen_role_id']}>" if guild_data.get("citizen_role_id") else None
        description = (
            f"Vote by clicking a candidate button below.\n\n"
            f"Candidates:\n{candidates_text}\n\n"
            f"Voting closes {format_timestamp(voting_end, 'R')}"
        )
        voting_type = VotingType.ELECTION

    embed = create_embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime_now(),
    )

    ballot_message = await channel.send(
        content=content,
        embed=embed,
        view=ElectionVotingView(client, db_helper, voting["$id"], candidates, voting_type=voting_type),
    )

    await db_helper.update_voting(
        voting["$id"],
        {"status": VotingStatus.VOTING.value, "message_id": str(ballot_message.id)},
    )
    return True


@tasks.loop(hours=24)
async def election_scheduler_loop():
    """Queue and execute election/chancellor election notices + auto announcements."""
    now = datetime_now()
    tomorrow = now + timedelta(days=1)

    for guild in client.guilds:
        guild_data = await db_helper.get_guild(guild.id)
        if not guild_data or not guild_data.get("enabled", True):
            continue

        max_councillors = int(guild_data.get("max_councillors", 9))
        active_councillors = await db_helper.list_councillors(guild.id, active_only=True)
        is_full_council = len(active_councillors) >= max_councillors

        for voting_type in [VotingType.ELECTION, VotingType.CHANCELLOR_ELECTION]:
            pending = await _find_voting(guild.id, voting_type, VotingStatus.PENDING)
            active = await _find_voting(guild.id, voting_type, VotingStatus.VOTING)
            if pending or active:
                continue

            schedule_key = AUTOMATION_SCHEDULE_KEYS[voting_type]
            schedule = await _get_schedule(guild.id, schedule_key)

            if not schedule or not schedule.get("run_date"):
                last_end = await _latest_voting_end(guild.id, voting_type)
                older_than_month = (last_end is None) or ((now - last_end) > timedelta(days=30))

                should_schedule = (
                    (is_full_council and tomorrow.day == 1)
                    or ((not is_full_council) and older_than_month)
                )
                if should_schedule:
                    schedule = {
                        "notice_date": now.date().isoformat(),
                        "run_date": tomorrow.date().isoformat(),
                        "notice_sent": False,
                    }
                    await _set_schedule(guild.id, schedule_key, schedule)

            if not schedule or not schedule.get("run_date"):
                continue

            run_date = datetime.fromisoformat(schedule["run_date"])
            notice_date = datetime.fromisoformat(schedule["notice_date"])

            if not schedule.get("notice_sent") and now.date() >= notice_date.date():
                await _send_president_notice(guild, guild_data, voting_type, run_date)
                schedule["notice_sent"] = True
                await _set_schedule(guild.id, schedule_key, schedule)

            if now.date() >= run_date.date():
                announced = await _auto_announce_election(guild, guild_data, voting_type)
                if announced:
                    log(f"Auto-announced {voting_type.value} for guild {guild.id}", "INFO")
                await _clear_schedule(guild.id, schedule_key)


@election_scheduler_loop.before_loop
async def _before_election_scheduler_loop():
    await client.wait_until_ready()
    if not config.DEBUG_MODE:
        wait = seconds_until(0, 1)  # First run shortly after midnight UTC.
        await asyncio.sleep(wait)


@tasks.loop(minutes=30)
async def update_votings():
    """Check and update voting statuses."""
    log("Running voting update task...", "INFO")
    current_datetime = datetime_now()

    try:
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

            if not (start_dt <= current_datetime or config.DEBUG_MODE):
                continue

            guild_id = doc["council_id"].replace("_c", "")
            guild = client.get_guild(int(guild_id))
            if not guild:
                continue
            guild_data = await db_helper.get_guild(guild.id)
            if not guild_data:
                continue

            if doc.get("type") in [VotingType.ELECTION.value, VotingType.CHANCELLOR_ELECTION.value]:
                started = await _auto_start_pending_election(doc, guild, guild_data)
                if started:
                    log(f"Activated election voting {doc['$id']} (pending → voting)", "INFO")
            else:
                await db_helper.update_voting(doc["$id"], {"status": VotingStatus.VOTING.value})
                log(f"Activated voting {doc['$id']} (pending → voting)", "INFO")

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

        if not election_scheduler_loop.is_running():
            election_scheduler_loop.start()
            log("Started election scheduler task", "SUCCESS")

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
