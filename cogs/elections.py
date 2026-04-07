"""
Elections Commands Cog
Handles council elections and chancellor elections
"""
import discord
from appwrite.query import Query
from discord import app_commands
from discord.ext import commands
from typing import Optional, cast
from datetime import datetime

from utils.database import DatabaseHelper
from utils.permissions import check_president, check_councillor, can_register_to_vote, can_run_for_councillor
from utils.errors import handle_interaction_error, AlreadyExistsError, NotFoundError, InvalidInputError
from utils.formatting import (
    create_success_message, create_error_message, create_embed, format_timestamp
)
from utils.helpers import datetime_now, convert_datetime_from_str, generate_keycap_emoji
from utils.enums import VotingType, VotingStatus, LogType


class ElectionRegistrationView(discord.ui.View):
    """View for election registration buttons"""

    def __init__(
        self,
        bot: commands.Bot,
        db_helper: DatabaseHelper,
        voting_id: str,
        voting_type: VotingType = VotingType.ELECTION,
    ):
        super().__init__(timeout=None)
        self.bot = bot
        self.db_helper = db_helper
        self.voting_id = voting_id
        self.voting_type = voting_type

    async def _require_active_councillor(self, interaction: discord.Interaction) -> bool:
        councillor = await self.db_helper.get_councillor(interaction.user.id, interaction.guild.id)
        if not councillor or not councillor.get("active", False):
            await interaction.response.send_message(
                create_error_message("Only active councillors can participate in chancellor elections."),
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="Register to Vote", style=discord.ButtonStyle.green, emoji="🗳️")
    async def register_voter(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Register as a voter"""
        try:
            if self.voting_type == VotingType.CHANCELLOR_ELECTION:
                if not await self._require_active_councillor(interaction):
                    return
            else:
                can_vote, reason = await can_register_to_vote(interaction.user, interaction.guild, self.db_helper)
                if not can_vote:
                    await interaction.response.send_message(
                        create_error_message(f"Not eligible: {reason}"),
                        ephemeral=True
                    )
                    return

            voters = await self.db_helper.get_registered_voters(self.voting_id)
            if any(voter["discord_id"] == str(interaction.user.id) for voter in voters):
                await interaction.response.send_message(
                    create_error_message("You are already registered to vote!"),
                    ephemeral=True,
                )
                return

            await self.db_helper.register_voter(
                voting_id=self.voting_id,
                discord_id=interaction.user.id,
                name=interaction.user.name,
            )
            await interaction.response.send_message(
                create_success_message("You have been registered to vote in this election!"),
                ephemeral=True,
            )
        except Exception as e:
            await handle_interaction_error(interaction, e)

    @discord.ui.button(label="Run for Office", style=discord.ButtonStyle.blurple, emoji="🏛️")
    async def register_candidate(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Register as a candidate"""
        try:
            if self.voting_type == VotingType.CHANCELLOR_ELECTION:
                if not await self._require_active_councillor(interaction):
                    return
            else:
                can_run, reason = await can_run_for_councillor(interaction.user, interaction.guild, self.db_helper)
                if not can_run:
                    await interaction.response.send_message(
                        create_error_message(f"Not eligible: {reason}"),
                        ephemeral=True
                    )
                    return

            guild_data = await self.db_helper.get_guild(interaction.guild.id)
            max_candidates = guild_data.get("max_councillors", 9)
            if self.voting_type == VotingType.CHANCELLOR_ELECTION:
                # Chancellor election candidate pool is active councillors.
                max_candidates = len(await self.db_helper.list_councillors(interaction.guild.id, active_only=True))

            candidates = await self.db_helper.get_candidates(self.voting_id)
            if len(candidates) >= max_candidates:
                await interaction.response.send_message(
                    create_error_message(f"Maximum number of candidates ({max_candidates}) reached!"),
                    ephemeral=True,
                )
                return

            if any(candidate["discord_id"] == str(interaction.user.id) for candidate in candidates):
                await interaction.response.send_message(
                    create_error_message("You are already registered as a candidate!"),
                    ephemeral=True,
                )
                return

            await self.db_helper.register_candidate(
                voting_id=self.voting_id,
                discord_id=interaction.user.id,
                name=interaction.user.name,
            )
            success_text = "You have been registered as a candidate! Good luck!"
            if self.voting_type == VotingType.CHANCELLOR_ELECTION:
                success_text = "You have been registered as a Chancellor candidate!"
            await interaction.response.send_message(create_success_message(success_text), ephemeral=True)
        except Exception as e:
            await handle_interaction_error(interaction, e)


class ElectionVotingView(discord.ui.View):
    """View for casting election votes"""

    def __init__(
        self,
        bot: commands.Bot,
        db_helper: DatabaseHelper,
        voting_id: str,
        candidates: list[dict],
        voting_type: VotingType = VotingType.ELECTION,
    ):
        super().__init__(timeout=None)
        self.bot = bot
        self.db_helper = db_helper
        self.voting_id = voting_id
        self.voting_type = voting_type

        for i, candidate in enumerate(candidates[:25], start=1):
            button = discord.ui.Button(
                label=candidate["name"][:80],
                style=discord.ButtonStyle.primary,
                emoji=generate_keycap_emoji(i),
                custom_id=f"election_vote_{voting_id}_{candidate['$id']}",
            )
            button.callback = self._make_vote_callback(candidate["$id"], candidate["name"])
            self.add_item(button)

    def _make_vote_callback(self, candidate_id: str, candidate_name: str):
        async def callback(interaction: discord.Interaction):
            await self.cast_vote(interaction, candidate_id, candidate_name)

        return callback

    async def cast_vote(self, interaction: discord.Interaction, candidate_id: str, candidate_name: str):
        """Cast one election vote for a candidate"""
        try:
            voting = await self.db_helper.get_voting(self.voting_id)
            if not voting:
                raise NotFoundError("Election not found.")
            if voting.get("status") != VotingStatus.VOTING.value:
                raise InvalidInputError("Voting is not open for this election.")

            if (voting.get("type") == VotingType.CHANCELLOR_ELECTION.value) or (
                self.voting_type == VotingType.CHANCELLOR_ELECTION
            ):
                councillor = await self.db_helper.get_councillor(interaction.user.id, interaction.guild.id)
                if not councillor or not councillor.get("active", False):
                    await interaction.response.send_message(
                        create_error_message("Only active councillors can vote in chancellor elections."),
                        ephemeral=True,
                    )
                    return

            voters = await self.db_helper.get_registered_voters(self.voting_id)
            voter = next((v for v in voters if v["discord_id"] == str(interaction.user.id)), None)
            if not voter:
                await interaction.response.send_message(
                    create_error_message("You must register before you can vote."),
                    ephemeral=True,
                )
                return

            if voter.get("has_voted", False):
                await interaction.response.send_message(
                    create_error_message("You have already voted in this election."),
                    ephemeral=True,
                )
                return

            candidate = await self.db_helper.get_candidate(candidate_id)
            if not candidate or candidate.get("voting_id") != self.voting_id:
                raise NotFoundError("Candidate not found for this election.")

            await self.db_helper.cast_vote(
                voting_id=self.voting_id,
                stance=True,
                discord_id=interaction.user.id,
                candidate_id=candidate_id,
            )
            await self.db_helper.update_voter(voter["$id"], {"has_voted": True})
            await self.db_helper.update_candidate(
                candidate_id,
                {"vote_count": int(candidate.get("vote_count", 0)) + 1},
            )

            await self.db_helper.log(
                guild_id=interaction.guild.id,
                log_type=LogType.VOTE,
                action="cast_election_vote",
                discord_id=interaction.user.id,
                details={"voting_id": self.voting_id, "candidate_id": candidate_id},
            )

            await interaction.response.send_message(
                create_success_message(f"Your vote for **{candidate_name}** has been recorded!"),
                ephemeral=True,
            )
        except Exception as e:
            await handle_interaction_error(interaction, e)


class Elections(commands.Cog):
    """Election management commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_helper = cast(DatabaseHelper, getattr(bot, "db_helper"))

    async def _find_voting(self, guild_id: int, voting_type: VotingType, status: VotingStatus) -> Optional[dict]:
        council_id = f"{guild_id}_c"
        result = self.db_helper.tables.list_rows(
            database_id=self.db_helper.db_id,
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

    async def _find_election(self, guild_id: int, status: VotingStatus) -> Optional[dict]:
        return await self._find_voting(guild_id, VotingType.ELECTION, status)

    async def _finalize_election(self, voting: dict, guild: discord.Guild) -> tuple[list[dict], bool]:
        candidates = await self.db_helper.get_candidates(voting["$id"])
        candidates.sort(key=lambda c: c.get("vote_count", 0), reverse=True)

        guild_data = await self.db_helper.get_guild(guild.id)
        max_councillors = guild_data.get("max_councillors", 9)

        councillor_role = None
        if guild_data.get("councillor_role_id"):
            councillor_role = guild.get_role(int(guild_data["councillor_role_id"]))

        chancellor_role = None
        if guild_data.get("chancellor_role_id"):
            chancellor_role = guild.get_role(int(guild_data["chancellor_role_id"]))

        current_councillors = await self.db_helper.list_councillors(guild.id, active_only=True)
        for councillor in current_councillors:
            await self.db_helper.update_councillor(councillor["$id"], {"active": False, "is_chancellor": False})
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

        elected: list[dict] = []
        for candidate in candidates[:max_councillors]:
            existing = await self.db_helper.get_councillor(candidate["discord_id"], guild.id)
            if existing:
                await self.db_helper.update_councillor(
                    existing["$id"],
                    {"active": True, "is_chancellor": False, "name": candidate["name"]},
                )
            else:
                await self.db_helper.create_councillor(
                    discord_id=candidate["discord_id"],
                    name=candidate["name"],
                    guild_id=guild.id,
                )

            await self.db_helper.update_candidate(candidate["$id"], {"elected": True})
            elected.append(candidate)

            member = guild.get_member(int(candidate["discord_id"]))
            if member and councillor_role and councillor_role not in member.roles:
                try:
                    await member.add_roles(councillor_role, reason="Elected to council")
                except discord.HTTPException:
                    pass

        await self.db_helper.update_voting(
            voting["$id"],
            {"status": VotingStatus.PASSED.value, "result_announced": True},
        )
        await self.db_helper.update_council(
            guild.id,
            {"election_in_progress": False, "current_chancellor_id": None},
        )

        return elected, councillor_role is not None

    @app_commands.command(name="announce_election", description="[President] Announce a council election")
    @app_commands.describe(
        start_date="Start date (format: DD.MM.YYYY HH:MM)",
        end_date="End date (format: DD.MM.YYYY HH:MM)",
        channel="Channel to post announcement (optional)",
        ping_everyone="Whether to ping @everyone",
    )
    async def announce_election(
        self,
        interaction: discord.Interaction,
        start_date: str,
        end_date: str,
        channel: Optional[discord.TextChannel] = None,
        ping_everyone: bool = False,
    ):
        """Announce a new council election"""
        try:
            await check_president(interaction.user, interaction.guild, self.db_helper)

            # Parse dates
            start_dt = convert_datetime_from_str(start_date)
            end_dt = convert_datetime_from_str(end_date)

            if not start_dt or not end_dt:
                raise InvalidInputError(
                    "Invalid date format. Use: DD.MM.YYYY HH:MM (e.g., 24.12.2025 23:56)"
                )

            if end_dt <= start_dt:
                raise InvalidInputError("End date must be after start date.")

            # Check for existing pending election
            council_data = await self.db_helper.get_council(interaction.guild.id)
            if council_data and council_data.get("election_in_progress"):
                raise AlreadyExistsError("An election is already in progress!")

            # Determine channel
            if not channel:
                guild_data = await self.db_helper.get_guild(interaction.guild.id)
                channel_id = guild_data.get("announcement_channel_id") or guild_data.get("voting_channel_id")
                if channel_id:
                    channel = interaction.guild.get_channel(int(channel_id))

            if not channel:
                raise NotFoundError("No announcement channel configured or specified.")

            # Create announcement embed
            embed = create_embed(
                title="🗳️ Council Election Announced!",
                description=(
                    f"## Election Alert!\n\n"
                    f"Citizens of {interaction.guild.name}, it's time to elect new members to the Grand Council!\n\n"
                    f"### 📅 Election Period\n"
                    f"**Registration & Campaigning:** `now`\n"
                    f"**Voting Begins:** {format_timestamp(start_dt, 'R')}\n"
                    f"**Voting Ends:** {format_timestamp(end_dt, 'R')}\n\n"
                    f"### 📋 How to Participate\n"
                    f"• **Vote:** Click 'Register to Vote' below\n"
                    f"• **Run for Council:** Click 'Run for Councillor' below\n\n"
                    f"### ✅ Eligibility\n"
                    f"Check your eligibility with `/council` command.\n\n"
                    f"Make your voice heard! Register now and shape the future of {interaction.guild.name}! 🏛️"
                ),
                color=0x00B0F4,
                timestamp=datetime_now()
            )

            embed.set_footer(text="Democracy in Action")

            # Send announcement
            view = ElectionRegistrationView(self.bot, self.db_helper, "pending")
            content = "@everyone" if ping_everyone else None
            message = await channel.send(content=content, embed=embed, view=view)

            # Create voting record
            voting = await self.db_helper.create_voting(
                voting_type=VotingType.ELECTION,
                title="Council Election",
                description="Election for new Grand Council members",
                guild_id=interaction.guild.id,
                voting_start=start_dt,
                voting_end=end_dt,
                status=VotingStatus.PENDING,
                message_id=str(message.id),
                required_percentage=0.0  # Elections don't use percentage
            )

            # Update council
            await self.db_helper.update_council(
                interaction.guild.id,
                {'election_in_progress': True}
            )

            # Update view with correct voting ID
            view = ElectionRegistrationView(self.bot, self.db_helper, voting['$id'])
            await message.edit(view=view)

            # Log action
            await self.db_helper.log(
                guild_id=interaction.guild.id,
                log_type=LogType.ELECTION,
                action="announce_election",
                discord_id=interaction.user.id,
                details={'voting_id': voting['$id']}
            )

            await interaction.response.send_message(
                create_success_message(f"Election announced in {channel.mention}!"),
                ephemeral=True
            )
        except Exception as e:
            await handle_interaction_error(interaction, e)

    @app_commands.command(name="start_voting", description="[President] Start voting for the pending election")
    @app_commands.describe(channel="Channel to post the voting ballot (optional)")
    async def start_voting(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
    ):
        """Start election voting phase"""
        try:
            await check_president(interaction.user, interaction.guild, self.db_helper)

            voting = await self._find_election(interaction.guild.id, VotingStatus.PENDING)
            if not voting:
                raise NotFoundError("No pending election found.")

            candidates = await self.db_helper.get_candidates(voting["$id"])
            if not candidates:
                raise InvalidInputError("No candidates have registered yet.")

            if not channel:
                guild_data = await self.db_helper.get_guild(interaction.guild.id)
                channel_id = guild_data.get("voting_channel_id") or guild_data.get("announcement_channel_id")
                if channel_id:
                    channel = interaction.guild.get_channel(int(channel_id))
            if not channel:
                raise NotFoundError("No voting channel configured or specified.")

            candidates_text = "\n".join(
                f"{generate_keycap_emoji(i)} {candidate['name']}"
                for i, candidate in enumerate(candidates[:25], start=1)
            )

            voting_end = datetime.fromisoformat(voting["voting_end"].replace("Z", "+00:00"))
            embed = create_embed(
                title="Council Election - Voting Open",
                description=(
                    f"Vote by clicking a candidate button below.\n\n"
                    f"Candidates:\n{candidates_text}\n\n"
                    f"Voting closes {format_timestamp(voting_end, 'R')}"
                ),
                color=0x00FF00,
                timestamp=datetime_now(),
            )
            embed.set_footer(text=f"Election ID: {voting['$id']}")

            guild_data = await self.db_helper.get_guild(interaction.guild.id)
            content = f"<@&{guild_data['citizen_role_id']}>" if guild_data.get("citizen_role_id") else None
            ballot_message = await channel.send(
                content=content,
                embed=embed,
                view=ElectionVotingView(self.bot, self.db_helper, voting["$id"], candidates),
            )

            await self.db_helper.update_voting(
                voting["$id"],
                {"status": VotingStatus.VOTING.value, "message_id": str(ballot_message.id)},
            )

            await self.db_helper.log(
                guild_id=interaction.guild.id,
                log_type=LogType.ELECTION,
                action="start_voting",
                discord_id=interaction.user.id,
                details={"voting_id": voting["$id"], "candidates": len(candidates)},
            )

            await interaction.response.send_message(
                create_success_message(f"Voting has started in {channel.mention}!"),
                ephemeral=True,
            )
        except Exception as e:
            await handle_interaction_error(interaction, e)

    @app_commands.command(name="close_election", description="[President] Close election and elect winners")
    async def close_election(self, interaction: discord.Interaction):
        """Close election and assign councillor roles"""
        try:
            # Acknowledge immediately because DB + role sync can take longer than 3 seconds.
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True, thinking=True)

            await check_president(interaction.user, interaction.guild, self.db_helper)

            voting = await self._find_election(interaction.guild.id, VotingStatus.VOTING)
            if not voting:
                raise NotFoundError("No active election found.")

            elected, roles_configured = await self._finalize_election(voting, interaction.guild)

            results = "\n".join(
                f"{idx}. {candidate['name']} - {candidate.get('vote_count', 0)} votes"
                for idx, candidate in enumerate(elected, start=1)
            ) or "No candidates received votes."

            total_votes = len(await self.db_helper.get_votes_for_voting(voting["$id"]))

            embed = create_embed(
                title="Election Results",
                description=(
                    f"{results}\n\n"
                    f"Total votes cast: {total_votes}\n"
                    f"Councillors elected: {len(elected)}\n"
                ),
                color=0xFFD700,
                timestamp=datetime_now(),
            )

            guild_data = await self.db_helper.get_guild(interaction.guild.id)
            channel_id = guild_data.get("announcement_channel_id") or guild_data.get("voting_channel_id")
            if channel_id:
                result_channel = interaction.guild.get_channel(int(channel_id))
                if result_channel:
                    await result_channel.send(embed=embed)

            await self.db_helper.log(
                guild_id=interaction.guild.id,
                log_type=LogType.ELECTION,
                action="close_election",
                discord_id=interaction.user.id,
                details={"voting_id": voting["$id"], "elected": len(elected)},
            )

            await interaction.followup.send(
                create_success_message(f"Election closed. {len(elected)} councillors elected."),
                ephemeral=True,
            )
        except Exception as e:
            await handle_interaction_error(interaction, e)

    @app_commands.command(
        name="announce_chancellor_election",
        description="[Councillor] Announce a chancellor election",
    )
    @app_commands.describe(
        registration_end="Registration end date (format: DD.MM.YYYY HH:MM)",
        voting_end="Voting end date (format: DD.MM.YYYY HH:MM)",
        channel="Channel to post election message (optional)",
    )
    async def announce_chancellor_election(
        self,
        interaction: discord.Interaction,
        registration_end: str,
        voting_end: str,
        channel: Optional[discord.TextChannel] = None,
    ):
        """Announce chancellor election (registration phase)"""
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True, thinking=True)

            await check_councillor(interaction.user, interaction.guild, self.db_helper)

            reg_end_dt = convert_datetime_from_str(registration_end)
            vote_end_dt = convert_datetime_from_str(voting_end)
            if not reg_end_dt or not vote_end_dt:
                raise InvalidInputError("Invalid date format. Use: DD.MM.YYYY HH:MM")
            if vote_end_dt <= reg_end_dt:
                raise InvalidInputError("Voting end must be after registration end.")

            existing_pending = await self._find_voting(
                interaction.guild.id,
                VotingType.CHANCELLOR_ELECTION,
                VotingStatus.PENDING,
            )
            existing_voting = await self._find_voting(
                interaction.guild.id,
                VotingType.CHANCELLOR_ELECTION,
                VotingStatus.VOTING,
            )
            if existing_pending or existing_voting:
                raise AlreadyExistsError("A chancellor election is already in progress!")

            councillors = await self.db_helper.list_councillors(interaction.guild.id, active_only=True)
            if not councillors:
                raise InvalidInputError("No active councillors available for chancellor election.")

            if not channel:
                guild_data = await self.db_helper.get_guild(interaction.guild.id)
                channel_id = guild_data.get("announcement_channel_id") or guild_data.get("voting_channel_id")
                if channel_id:
                    channel = interaction.guild.get_channel(int(channel_id))
            if not channel:
                raise NotFoundError("No channel configured or specified.")

            embed = create_embed(
                title="👑 Chancellor Election Announced",
                description=(
                    f"Only active councillors may register and vote.\n\n"
                    f"Registration closes {format_timestamp(reg_end_dt, 'R')}\n"
                    f"Voting closes {format_timestamp(vote_end_dt, 'R')}\n\n"
                    f"Use the buttons below to register as voter or candidate."
                ),
                color=0xFFD700,
                timestamp=datetime_now(),
            )
            embed.set_footer(text="Chancellor Election")

            pre_view = ElectionRegistrationView(
                self.bot,
                self.db_helper,
                "pending",
                voting_type=VotingType.CHANCELLOR_ELECTION,
            )
            guild_data = await self.db_helper.get_guild(interaction.guild.id)
            content = (
                f"<@&{guild_data['councillor_role_id']}>"
                if guild_data.get("councillor_role_id")
                else None
            )
            message = await channel.send(content=content, embed=embed, view=pre_view)

            voting = await self.db_helper.create_voting(
                voting_type=VotingType.CHANCELLOR_ELECTION,
                title="Chancellor Election",
                description="Election for Chancellor of the Grand Council",
                guild_id=interaction.guild.id,
                voting_start=reg_end_dt,
                voting_end=vote_end_dt,
                status=VotingStatus.PENDING,
                message_id=str(message.id),
                required_percentage=0.0,
            )

            await message.edit(
                view=ElectionRegistrationView(
                    self.bot,
                    self.db_helper,
                    voting["$id"],
                    voting_type=VotingType.CHANCELLOR_ELECTION,
                )
            )

            await self.db_helper.log(
                guild_id=interaction.guild.id,
                log_type=LogType.ELECTION,
                action="announce_chancellor_election",
                discord_id=interaction.user.id,
                details={"voting_id": voting["$id"]},
            )

            await interaction.followup.send(
                create_success_message(
                    f"Chancellor election announced in {channel.mention}. "
                    f"Start voting later with `/start_chancellor_voting`."
                ),
                ephemeral=True,
            )
        except Exception as e:
            await handle_interaction_error(interaction, e)

    @app_commands.command(
        name="start_chancellor_voting",
        description="[Councillor] Start voting for pending chancellor election",
    )
    @app_commands.describe(channel="Channel to post the voting ballot (optional)")
    async def start_chancellor_voting(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
    ):
        """Start chancellor election voting phase"""
        try:
            await check_councillor(interaction.user, interaction.guild, self.db_helper)

            voting = await self._find_voting(
                interaction.guild.id,
                VotingType.CHANCELLOR_ELECTION,
                VotingStatus.PENDING,
            )
            if not voting:
                raise NotFoundError("No pending chancellor election found.")

            candidates = await self.db_helper.get_candidates(voting["$id"])
            if not candidates:
                raise InvalidInputError("No candidates have registered yet.")

            voters = await self.db_helper.get_registered_voters(voting["$id"])
            if not voters:
                raise InvalidInputError("No voters have registered yet.")

            if not channel:
                guild_data = await self.db_helper.get_guild(interaction.guild.id)
                channel_id = guild_data.get("voting_channel_id") or guild_data.get("announcement_channel_id")
                if channel_id:
                    channel = interaction.guild.get_channel(int(channel_id))
            if not channel:
                raise NotFoundError("No voting channel configured or specified.")

            candidates_text = "\n".join(
                f"{generate_keycap_emoji(i)} {candidate['name']}"
                for i, candidate in enumerate(candidates[:25], start=1)
            )
            voting_end = datetime.fromisoformat(voting["voting_end"].replace("Z", "+00:00"))

            embed = create_embed(
                title="👑 Chancellor Election - Voting Open",
                description=(
                    f"Only registered councillors may vote.\n\n"
                    f"Candidates:\n{candidates_text}\n\n"
                    f"Voting closes {format_timestamp(voting_end, 'R')}"
                ),
                color=0xFFD700,
                timestamp=datetime_now(),
            )
            embed.set_footer(text=f"Chancellor Election ID: {voting['$id']}")

            guild_data = await self.db_helper.get_guild(interaction.guild.id)
            content = (
                f"<@&{guild_data['councillor_role_id']}>"
                if guild_data.get("councillor_role_id")
                else None
            )
            message = await channel.send(
                content=content,
                embed=embed,
                view=ElectionVotingView(
                    self.bot,
                    self.db_helper,
                    voting["$id"],
                    candidates,
                    voting_type=VotingType.CHANCELLOR_ELECTION,
                ),
            )

            await self.db_helper.update_voting(
                voting["$id"],
                {"status": VotingStatus.VOTING.value, "message_id": str(message.id)},
            )

            await self.db_helper.log(
                guild_id=interaction.guild.id,
                log_type=LogType.ELECTION,
                action="start_chancellor_voting",
                discord_id=interaction.user.id,
                details={"voting_id": voting["$id"], "candidates": len(candidates), "voters": len(voters)},
            )

            await interaction.response.send_message(
                create_success_message(f"Chancellor voting has started in {channel.mention}!"),
                ephemeral=True,
            )
        except Exception as e:
            await handle_interaction_error(interaction, e)

    @app_commands.command(
        name="close_chancellor_election",
        description="[Councillor] Close chancellor election and elect winner",
    )
    async def close_chancellor_election(self, interaction: discord.Interaction):
        """Close active chancellor election and assign the winner"""
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True, thinking=True)

            await check_councillor(interaction.user, interaction.guild, self.db_helper)

            voting = await self._find_voting(
                interaction.guild.id,
                VotingType.CHANCELLOR_ELECTION,
                VotingStatus.VOTING,
            )
            if not voting:
                raise NotFoundError("No active chancellor election found.")

            candidates = await self.db_helper.get_candidates(voting["$id"])
            candidates.sort(key=lambda c: c.get("vote_count", 0), reverse=True)
            if not candidates or int(candidates[0].get("vote_count", 0)) <= 0:
                raise InvalidInputError("No votes have been cast yet.")

            winner = candidates[0]
            guild_data = await self.db_helper.get_guild(interaction.guild.id)
            chancellor_role = None
            if guild_data.get("chancellor_role_id"):
                chancellor_role = interaction.guild.get_role(int(guild_data["chancellor_role_id"]))

            all_councillors = await self.db_helper.list_councillors(interaction.guild.id, active_only=False)
            for councillor in all_councillors:
                await self.db_helper.update_councillor(councillor["$id"], {"is_chancellor": False})
                if chancellor_role:
                    member = interaction.guild.get_member(int(councillor["discord_id"]))
                    if member and chancellor_role in member.roles:
                        try:
                            await member.remove_roles(chancellor_role, reason="New chancellor elected")
                        except discord.HTTPException:
                            pass

            winner_councillor = await self.db_helper.get_councillor(winner["discord_id"], interaction.guild.id)
            if winner_councillor:
                await self.db_helper.update_councillor(winner_councillor["$id"], {"is_chancellor": True})

            if chancellor_role:
                member = interaction.guild.get_member(int(winner["discord_id"]))
                if member and chancellor_role not in member.roles:
                    try:
                        await member.add_roles(chancellor_role, reason="Elected as Chancellor")
                    except discord.HTTPException:
                        pass

            await self.db_helper.update_candidate(winner["$id"], {"elected": True})
            await self.db_helper.update_council(
                interaction.guild.id,
                {"current_chancellor_id": str(winner["discord_id"])},
            )
            await self.db_helper.update_voting(
                voting["$id"],
                {"status": VotingStatus.PASSED.value, "result_announced": True},
            )

            results_text = "\n".join(
                f"{idx}. {candidate['name']} - {candidate.get('vote_count', 0)} votes"
                for idx, candidate in enumerate(candidates[:10], start=1)
            )

            embed = create_embed(
                title="Chancellor Election Results",
                description=(
                    f"**{winner['name']}** has been elected Chancellor.\n\n"
                    f"Final results:\n{results_text}\n\n"
                ),
                color=0xFFD700,
                timestamp=datetime_now(),
            )

            channel_id = guild_data.get("announcement_channel_id") or guild_data.get("voting_channel_id")
            if channel_id:
                channel = interaction.guild.get_channel(int(channel_id))
                if channel:
                    await channel.send(embed=embed)

            await self.db_helper.log(
                guild_id=interaction.guild.id,
                log_type=LogType.ELECTION,
                action="close_chancellor_election",
                discord_id=interaction.user.id,
                details={"voting_id": voting["$id"], "winner": winner["name"]},
            )

            await interaction.followup.send(
                create_success_message(f"Chancellor election closed. Winner: **{winner['name']}**."),
                ephemeral=True,
            )
        except Exception as e:
            await handle_interaction_error(interaction, e)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Elections(bot))
