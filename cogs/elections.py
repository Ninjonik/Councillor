"""
Elections Commands Cog
Handles council elections and chancellor elections
"""
import discord
from appwrite.query import Query
from discord import app_commands
from discord.ext import commands
from typing import Optional
from datetime import datetime

from utils.database import DatabaseHelper
from utils.permissions import check_president, check_admin, can_register_to_vote, can_run_for_councillor, check_councillor, is_eligible
from utils.errors import handle_interaction_error, AlreadyExistsError, NotFoundError, InvalidInputError
from utils.formatting import (
    create_success_message, create_error_message, create_embed,
    format_timestamp, format_bold
)
from utils.helpers import datetime_now, convert_datetime_from_str, generate_keycap_emoji, parse_iso_datetime
from utils.enums import VotingType, VotingStatus, LogType, RoleType


class ElectionRegistrationView(discord.ui.View):
    """View for election registration buttons"""

    def __init__(self, bot: commands.Bot, db_helper: DatabaseHelper, voting_id: str):
        super().__init__(timeout=None)
        self.bot = bot
        self.db_helper = db_helper
        self.voting_id = voting_id

    @discord.ui.button(label="Register to Vote", style=discord.ButtonStyle.green, emoji="🗳️")
    async def register_voter(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Register as a voter"""
        try:
            # Check eligibility
            can_vote, reason = await can_register_to_vote(
                interaction.user, interaction.guild, self.db_helper
            )

            if not can_vote:
                await interaction.response.send_message(
                    create_error_message(f"Not eligible: {reason}"),
                    ephemeral=True
                )
                return

            # Check if already registered
            voters = await self.db_helper.get_registered_voters(self.voting_id)
            for voter in voters:
                if voter['discord_id'] == str(interaction.user.id):
                    await interaction.response.send_message(
                        create_error_message("You are already registered to vote!"),
                        ephemeral=True
                    )
                    return

            # Register voter
            await self.db_helper.register_voter(
                voting_id=self.voting_id,
                discord_id=interaction.user.id,
                name=interaction.user.name
            )

            await interaction.response.send_message(
                create_success_message("You have been registered to vote in this election!"),
                ephemeral=True
            )

        except Exception as e:
            await handle_interaction_error(interaction, e)

    @discord.ui.button(label="Run for Councillor", style=discord.ButtonStyle.blurple, emoji="🏛️")
    async def register_candidate(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Register as a candidate"""
        try:
            # Check eligibility
            can_run, reason = await can_run_for_councillor(
                interaction.user, interaction.guild, self.db_helper
            )

            if not can_run:
                await interaction.response.send_message(
                    create_error_message(f"Not eligible: {reason}"),
                    ephemeral=True
                )
                return

            # Check max candidates
            guild_data = await self.db_helper.get_guild(interaction.guild.id)
            max_candidates = guild_data.get('max_councillors', 9)

            candidates = await self.db_helper.get_candidates(self.voting_id)
            if len(candidates) >= max_candidates:
                await interaction.response.send_message(
                    create_error_message(f"Maximum number of candidates ({max_candidates}) reached!"),
                    ephemeral=True
                )
                return

            # Check if already registered as candidate
            for candidate in candidates:
                if candidate['discord_id'] == str(interaction.user.id):
                    await interaction.response.send_message(
                        create_error_message("You are already registered as a candidate!"),
                        ephemeral=True
                    )
                    return

            # Register candidate
            await self.db_helper.register_candidate(
                voting_id=self.voting_id,
                discord_id=interaction.user.id,
                name=interaction.user.name
            )

            await interaction.response.send_message(
                create_success_message("You have been registered as a candidate! Good luck! 🍀"),
                ephemeral=True
            )

        except Exception as e:
            await handle_interaction_error(interaction, e)


class ElectionVotingView(discord.ui.View):
    """View for casting votes in elections"""

    def __init__(self, bot: commands.Bot, db_helper: DatabaseHelper, voting_id: str, candidates: list):
        super().__init__(timeout=None)
        self.bot = bot
        self.db_helper = db_helper
        self.voting_id = voting_id

        # Add buttons for each candidate (max 5 per row, max 25 total)
        for i, candidate in enumerate(candidates[:25]):
            button = discord.ui.Button(
                label=candidate['name'][:80],  # Discord limit
                style=discord.ButtonStyle.primary,
                emoji=generate_keycap_emoji(i),
                custom_id=f"vote_{candidate['$id']}"
            )
            button.callback = self.create_vote_callback(candidate['$id'], candidate['name'])
            self.add_item(button)

    def create_vote_callback(self, candidate_id: str, candidate_name: str):
        async def callback(interaction: discord.Interaction):
            await self.cast_vote(interaction, candidate_id, candidate_name)
        return callback

    async def cast_vote(self, interaction: discord.Interaction, candidate_id: str, candidate_name: str):
        """Handle vote casting for a candidate"""
        try:
            # Check if registered to vote
            voters = await self.db_helper.get_registered_voters(self.voting_id)
            voter = None
            for v in voters:
                if v['discord_id'] == str(interaction.user.id):
                    voter = v
                    break

            if not voter:
                await interaction.response.send_message(
                    create_error_message("You must register to vote before casting your ballot!"),
                    ephemeral=True
                )
                return

            # Check if already voted
            if voter.get('has_voted', False):
                await interaction.response.send_message(
                    create_error_message("You have already voted in this election!"),
                    ephemeral=True
                )
                return

            # Cast vote
            await self.db_helper.cast_vote(
                voting_id=self.voting_id,
                stance=True,  # For elections, stance is always True
                discord_id=interaction.user.id,
                candidate_id=candidate_id
            )

            # Mark voter as having voted
            await self.db_helper.update_voter(voter['$id'], {'has_voted': True})

            # Increment candidate vote count
            candidate = await self.db_helper.get_candidate(candidate_id)
            await self.db_helper.update_candidate(
                candidate_id,
                {'vote_count': candidate.get('vote_count', 0) + 1}
            )

            # Log the vote
            await self.db_helper.log(
                guild_id=interaction.guild.id,
                log_type=LogType.VOTE,
                action="cast_election_vote",
                discord_id=interaction.user.id,
                details={'voting_id': self.voting_id, 'candidate_id': candidate_id}
            )

            await interaction.response.send_message(
                create_success_message(f"Your vote for **{candidate_name}** has been recorded! 🗳️"),
                ephemeral=True
            )

        except Exception as e:
            await handle_interaction_error(interaction, e)


class Elections(commands.Cog):
    """Election management commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_helper: DatabaseHelper = bot.db_helper

    @app_commands.command(name='announce_election', description="[President] Announce a council election")
    @app_commands.describe(
        registration_end="Registration end date (format: DD.MM.YYYY HH:MM)",
        voting_end="Voting end date (format: DD.MM.YYYY HH:MM)",
        channel="Channel to post announcement (optional)",
        ping_everyone="Whether to ping @everyone"
    )
    async def announce_election(
        self,
        interaction: discord.Interaction,
        registration_end: str,
        voting_end: str,
        channel: Optional[discord.TextChannel] = None,
        ping_everyone: bool = False
    ):
        """Announce a new council election"""
        try:
            await check_president(interaction.user, interaction.guild, self.db_helper)

            # Parse dates
            reg_end_dt = convert_datetime_from_str(registration_end)
            vote_end_dt = convert_datetime_from_str(voting_end)

            if not reg_end_dt or not vote_end_dt:
                raise InvalidInputError(
                    "Invalid date format. Use: DD.MM.YYYY HH:MM (e.g., 24.12.2025 23:56)"
                )

            if vote_end_dt <= reg_end_dt:
                raise InvalidInputError("Voting end must be after registration end.")

            # Check for existing pending election
            council_data = await self.db_helper.get_council(interaction.guild.id)
            if council_data and council_data.get('election_in_progress'):
                raise AlreadyExistsError("An election is already in progress!")

            # Determine channel
            if not channel:
                guild_data = await self.db_helper.get_guild(interaction.guild.id)
                channel_id = guild_data.get('announcement_channel_id') or guild_data.get('voting_channel_id')
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
                    f"### 📅 Election Timeline\n"
                    f"**Registration Closes:** {format_timestamp(reg_end_dt, 'F')}\n"
                    f"**Voting Opens:** {format_timestamp(reg_end_dt, 'R')}\n"
                    f"**Voting Closes:** {format_timestamp(vote_end_dt, 'R')}\n\n"
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
            content = "@everyone" if ping_everyone else None
            message = await channel.send(content=content, embed=embed)

            # Create voting record
            voting = await self.db_helper.create_voting(
                voting_type=VotingType.ELECTION,
                title="Council Election",
                description="Election for new Grand Council members",
                guild_id=interaction.guild.id,
                voting_start=reg_end_dt,  # Voting starts when registration ends
                voting_end=vote_end_dt,
                status=VotingStatus.PENDING,
                message_id=str(message.id),
                required_percentage=0.0  # Elections don't use percentage
            )

            # Update council
            await self.db_helper.update_council(
                interaction.guild.id,
                {'election_in_progress': True}
            )

            # Add view with correct voting ID
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

    @app_commands.command(name='start_voting', description="[President] Start the voting phase of an election")
    @app_commands.describe(
        channel="Channel to post voting message (optional)"
    )
    async def start_voting(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None
    ):
        """Start voting phase for pending election"""
        try:
            await check_president(interaction.user, interaction.guild, self.db_helper)

            # Find pending election
            council_id = f"{interaction.guild.id}_c"
            result = self.db_helper.db.list_documents(
                database_id=self.db_helper.db_id,
                collection_id='votings',
                queries=[
                    Query.equal('council_id', council_id),
                    Query.equal('type', VotingType.ELECTION.value),
                    Query.equal('status', VotingStatus.PENDING.value),
                    Query.limit(1)
                ]
            )

            if result['total'] == 0:
                raise NotFoundError("No pending election found.")

            voting = result['documents'][0]

            # Get candidates
            candidates = await self.db_helper.get_candidates(voting['$id'])
            if len(candidates) == 0:
                raise InvalidInputError("No candidates have registered yet!")

            # Determine channel
            if not channel:
                guild_data = await self.db_helper.get_guild(interaction.guild.id)
                channel_id = guild_data.get('voting_channel_id') or guild_data.get('announcement_channel_id')
                if channel_id:
                    channel = interaction.guild.get_channel(int(channel_id))

            if not channel:
                raise NotFoundError("No voting channel configured or specified.")

            # Create voting embed
            candidates_text = "\n".join([
                f"{generate_keycap_emoji(i)} **{c['name']}**"
                for i, c in enumerate(candidates)
            ])

            # Parse voting end datetime from database (ISO format)
            voting_end_dt = parse_iso_datetime(voting['voting_end'])

            embed = create_embed(
                title="🗳️ Council Election - VOTING OPEN",
                description=(
                    f"## Cast Your Vote!\n\n"
                    f"The election is now open! Vote for the candidate(s) you want to see on the Council.\n\n"
                    f"### 📋 Candidates\n"
                    f"{candidates_text}\n\n"
                    f"### ⏰ Voting Closes\n"
                    f"{format_timestamp(voting_end_dt, 'R')}\n\n"
                    f"**Select a candidate below to vote!**"
                ),
                color=0x00FF00,
                timestamp=datetime_now()
            )

            embed.set_footer(text=f"Election ID: {voting['$id']}")

            # Send voting message
            view = ElectionVotingView(self.bot, self.db_helper, voting['$id'], candidates)

            content = None
            guild_data = await self.db_helper.get_guild(interaction.guild.id)
            if guild_data.get('citizen_role_id'):
                content = f"<@&{guild_data['citizen_role_id']}>"

            message = await channel.send(content=content, embed=embed, view=view)

            # Update voting status
            await self.db_helper.update_voting(
                voting['$id'],
                {
                    'status': VotingStatus.VOTING.value,
                    'message_id': str(message.id)
                }
            )

            # Log action
            await self.db_helper.log(
                guild_id=interaction.guild.id,
                log_type=LogType.ELECTION,
                action="start_voting",
                discord_id=interaction.user.id,
                details={'voting_id': voting['$id'], 'candidates': len(candidates)}
            )

            await interaction.response.send_message(
                create_success_message(
                    f"Voting has started in {channel.mention}!\n"
                    f"{len(candidates)} candidates are running."
                ),
                ephemeral=True
            )

        except Exception as e:
            await handle_interaction_error(interaction, e)

    @app_commands.command(name='close_election', description="[President] Close election and elect winners")
    async def close_election(self, interaction: discord.Interaction):
        """Close the election and elect the top candidates"""
        try:
            await check_president(interaction.user, interaction.guild, self.db_helper)

            # Find active election
            council_id = f"{interaction.guild.id}_c"
            from appwrite.query import Query
            result = self.db_helper.db.list_documents(
                database_id=self.db_helper.db_id,
                collection_id='votings',
                queries=[
                    Query.equal('council_id', council_id),
                    Query.equal('type', VotingType.ELECTION.value),
                    Query.equal('status', VotingStatus.VOTING.value),
                    Query.limit(1)
                ]
            )

            if result['total'] == 0:
                raise NotFoundError("No active election found.")

            voting = result['documents'][0]

            # Get candidates sorted by vote count
            candidates = await self.db_helper.get_candidates(voting['$id'])
            candidates.sort(key=lambda x: x.get('vote_count', 0), reverse=True)

            # Determine how many to elect
            guild_data = await self.db_helper.get_guild(interaction.guild.id)
            max_councillors = guild_data.get('max_councillors', 9)

            # Get councillor role for Discord role management
            councillor_role_id = guild_data.get('councillor_role_id')
            councillor_role = None
            if councillor_role_id:
                councillor_role = interaction.guild.get_role(int(councillor_role_id))

            # Deactivate all current councillors and remove their roles
            current_councillors = await self.db_helper.list_councillors(interaction.guild.id)
            for councillor in current_councillors:
                await self.db_helper.update_councillor(councillor['$id'], {'active': False})

                # Remove councillor role from old councillors
                if councillor_role:
                    try:
                        member = interaction.guild.get_member(int(councillor['discord_id']))
                        if member and councillor_role in member.roles:
                            await member.remove_roles(councillor_role, reason="Council term ended - new election")
                    except Exception as e:
                        # Log but don't fail if role removal fails
                        print(f"Failed to remove role from {councillor['discord_id']}: {e}")

            # Elect top candidates
            elected = []
            for i, candidate in enumerate(candidates[:max_councillors]):
                if candidate.get('vote_count', 0) > 0:  # Only elect if they got votes
                    # Create councillor record
                    await self.db_helper.create_councillor(
                        discord_id=candidate['discord_id'],
                        name=candidate['name'],
                        guild_id=interaction.guild.id
                    )

                    # Mark as elected
                    await self.db_helper.update_candidate(candidate['$id'], {'elected': True})
                    elected.append(candidate)

                    # Give councillor role to newly elected councillors
                    if councillor_role:
                        try:
                            member = interaction.guild.get_member(int(candidate['discord_id']))
                            if member and councillor_role not in member.roles:
                                await member.add_roles(councillor_role, reason="Elected to Grand Council")
                        except Exception as e:
                            # Log but don't fail if role assignment fails
                            print(f"Failed to add role to {candidate['discord_id']}: {e}")

            # Update voting status
            await self.db_helper.update_voting(
                voting['$id'],
                {
                    'status': VotingStatus.PASSED.value,
                    'result_announced': True
                }
            )

            # Update council
            await self.db_helper.update_council(
                interaction.guild.id,
                {'election_in_progress': False}
            )

            # Create results embed
            results_text = "\n".join([
                f"**{i+1}.** {c['name']} - {c.get('vote_count', 0)} votes"
                for i, c in enumerate(elected)
            ])

            role_status = ""
            if councillor_role:
                role_status = f"\n\n✅ Councillor roles have been updated!"
            else:
                role_status = f"\n\n⚠️ No councillor role configured. Use `/set_role` to set one."

            embed = create_embed(
                title="🎉 Election Results",
                description=(
                    f"## The votes are in!\n\n"
                    f"The following candidates have been elected to the Grand Council:\n\n"
                    f"{results_text}\n\n"
                    f"**Total Votes Cast:** {len(await self.db_helper.get_votes_for_voting(voting['$id']))}\n"
                    f"**Councillors Elected:** {len(elected)}"
                    f"{role_status}\n\n"
                    f"Congratulations to the newly elected Councillors! 🏛️"
                ),
                color=0xFFD700,
                timestamp=datetime_now()
            )

            embed.set_footer(text="Democracy in Action")

            # Send results
            guild_data = await self.db_helper.get_guild(interaction.guild.id)
            channel_id = guild_data.get('announcement_channel_id') or guild_data.get('voting_channel_id')
            if channel_id:
                channel = interaction.guild.get_channel(int(channel_id))
                if channel:
                    await channel.send(embed=embed)

            # Log action
            await self.db_helper.log(
                guild_id=interaction.guild.id,
                log_type=LogType.ELECTION,
                action="close_election",
                discord_id=interaction.user.id,
                details={'voting_id': voting['$id'], 'elected': len(elected)}
            )

            await interaction.response.send_message(
                create_success_message(
                    f"Election closed! {len(elected)} councillors elected."
                    + (f"\n✅ Roles updated!" if councillor_role else f"\n⚠️ No councillor role set.")
                ),
                ephemeral=True
            )

        except Exception as e:
            await handle_interaction_error(interaction, e)

    # ============================================
    # Chancellor Election Commands
    # ============================================

    @app_commands.command(name='announce_chancellor_election', description="[Councillor] Announce a chancellor election")
    @app_commands.describe(
        voting_end="Voting end date (format: DD.MM.YYYY HH:MM)",
        channel="Channel to post announcement (optional)"
    )
    async def announce_chancellor_election(
        self,
        interaction: discord.Interaction,
        voting_end: str,
        channel: Optional[discord.TextChannel] = None
    ):
        """Announce a new chancellor election (councillors only)"""
        try:
            await check_councillor(interaction.user, interaction.guild, self.db_helper)

            # Parse date
            vote_end_dt = convert_datetime_from_str(voting_end)

            if not vote_end_dt:
                raise InvalidInputError(
                    "Invalid date format. Use: DD.MM.YYYY HH:MM (e.g., 24.12.2025 23:56)"
                )

            if vote_end_dt <= datetime_now():
                raise InvalidInputError("Voting end must be in the future.")

            # Check for existing active chancellor election
            council_id = f"{interaction.guild.id}_c"
            existing = self.db_helper.db.list_documents(
                database_id=self.db_helper.db_id,
                collection_id='votings',
                queries=[
                    Query.equal('council_id', council_id),
                    Query.equal('type', VotingType.CHANCELLOR_ELECTION.value),
                    Query.equal('status', VotingStatus.VOTING.value),
                    Query.limit(1)
                ]
            )

            if existing['total'] > 0:
                raise AlreadyExistsError("A chancellor election is already in progress!")

            # Determine channel
            if not channel:
                guild_data = await self.db_helper.get_guild(interaction.guild.id)
                channel_id = guild_data.get('voting_channel_id') or guild_data.get('announcement_channel_id')
                if channel_id:
                    channel = interaction.guild.get_channel(int(channel_id))

            if not channel:
                raise NotFoundError("No voting channel configured or specified.")

            # Get list of councillors
            councillors = await self.db_helper.list_councillors(interaction.guild.id, active_only=True)
            councillors_text = "\n".join([
                f"{generate_keycap_emoji(i)} **{c['name']}**"
                for i, c in enumerate(councillors[:25])
            ])

            # Create announcement embed
            embed = create_embed(
                title="👑 Chancellor Election Announced!",
                description=(
                    f"## Chancellor Election!\n\n"
                    f"The Grand Council will now elect a Chancellor to lead the Council!\n\n"
                    f"### 📅 Election Timeline\n"
                    f"**Voting Opens:** Now\n"
                    f"**Voting Closes:** {format_timestamp(vote_end_dt, 'R')}\n\n"
                    f"### 📋 How to Participate\n"
                    f"• **Vote:** Only councillors can vote - click a button below\n"
                    f"• **Eligible Candidates:** All active councillors\n\n"
                    f"### 🗳️ Current Councillors\n"
                    f"{councillors_text if councillors_text else 'No councillors available'}\n\n"
                    f"**Select a councillor below to vote for them as Chancellor!**"
                ),
                color=0xFFD700,
                timestamp=datetime_now()
            )

            embed.set_footer(text="Chancellor Election")

            # Create voting view with councillor buttons
            view = ElectionVotingView(self.bot, self.db_helper, "pending", councillors)

            # Send announcement
            guild_data = await self.db_helper.get_guild(interaction.guild.id)
            content = None
            if guild_data.get('councillor_role_id'):
                content = f"<@&{guild_data['councillor_role_id']}>"

            message = await channel.send(content=content, embed=embed, view=view)

            # Create voting record
            voting = await self.db_helper.create_voting(
                voting_type=VotingType.CHANCELLOR_ELECTION,
                title="Chancellor Election",
                description="Election for Chancellor of the Grand Council",
                guild_id=interaction.guild.id,
                voting_end=vote_end_dt,
                status=VotingStatus.VOTING,
                message_id=str(message.id),
                required_percentage=0.0  # Chancellor election uses simple majority
            )

            # Register all active councillors as candidates automatically
            for councillor in councillors:
                await self.db_helper.register_candidate(
                    voting_id=voting['$id'],
                    discord_id=councillor['discord_id'],
                    name=councillor['name']
                )

            # Register all councillors as voters automatically
            for councillor in councillors:
                await self.db_helper.register_voter(
                    voting_id=voting['$id'],
                    discord_id=councillor['discord_id'],
                    name=councillor['name']
                )

            # Update the view with the correct voting ID
            candidates = await self.db_helper.get_candidates(voting['$id'])
            view = ElectionVotingView(self.bot, self.db_helper, voting['$id'], candidates)

            # Update embed footer with voting ID
            embed.set_footer(text=f"Chancellor Election • ID: {voting['$id']}")
            await message.edit(embed=embed, view=view)

            # Log action
            await self.db_helper.log(
                guild_id=interaction.guild.id,
                log_type=LogType.ELECTION,
                action="announce_chancellor_election",
                discord_id=interaction.user.id,
                details={'voting_id': voting['$id']}
            )

            await interaction.response.send_message(
                create_success_message(
                    f"Chancellor election announced in {channel.mention}!\n"
                    f"Voting ends {format_timestamp(vote_end_dt, 'R')}"
                ),
                ephemeral=True
            )

        except Exception as e:
            await handle_interaction_error(interaction, e)

    @app_commands.command(name='close_chancellor_election', description="[Councillor] Close chancellor election and elect winner")
    async def close_chancellor_election(self, interaction: discord.Interaction):
        """Close the chancellor election and elect the winner"""
        try:
            await check_councillor(interaction.user, interaction.guild, self.db_helper)

            # Find active chancellor election
            council_id = f"{interaction.guild.id}_c"
            result = self.db_helper.db.list_documents(
                database_id=self.db_helper.db_id,
                collection_id='votings',
                queries=[
                    Query.equal('council_id', council_id),
                    Query.equal('type', VotingType.CHANCELLOR_ELECTION.value),
                    Query.equal('status', VotingStatus.VOTING.value),
                    Query.limit(1)
                ]
            )

            if result['total'] == 0:
                raise NotFoundError("No active chancellor election found.")

            voting = result['documents'][0]

            # Get candidates sorted by vote count
            candidates = await self.db_helper.get_candidates(voting['$id'])
            candidates.sort(key=lambda x: x.get('vote_count', 0), reverse=True)

            if len(candidates) == 0 or candidates[0].get('vote_count', 0) == 0:
                raise InvalidInputError("No votes have been cast yet!")

            # Get the winner (highest vote count)
            winner = candidates[0]

            # Get guild data for role management
            guild_data = await self.db_helper.get_guild(interaction.guild.id)
            chancellor_role_id = guild_data.get('chancellor_role_id')
            chancellor_role = None
            if chancellor_role_id:
                chancellor_role = interaction.guild.get_role(int(chancellor_role_id))

            # Remove chancellor role from previous chancellor
            council_data = await self.db_helper.get_council(interaction.guild.id)
            if council_data and council_data.get('current_chancellor_id'):
                old_chancellor_id = council_data['current_chancellor_id']
                # Find old chancellor councillor record
                old_councillors = await self.db_helper.list_councillors(interaction.guild.id, active_only=False)
                for councillor in old_councillors:
                    if councillor['$id'] == old_chancellor_id:
                        # Update database
                        await self.db_helper.update_councillor(councillor['$id'], {'is_chancellor': False})

                        # Remove role
                        if chancellor_role:
                            try:
                                member = interaction.guild.get_member(int(councillor['discord_id']))
                                if member and chancellor_role in member.roles:
                                    await member.remove_roles(chancellor_role, reason="Chancellor term ended - new election")
                            except Exception as e:
                                print(f"Failed to remove chancellor role from {councillor['discord_id']}: {e}")
                        break

            # Get the winner's councillor record and mark as chancellor
            winner_councillor = await self.db_helper.get_councillor(winner['discord_id'], interaction.guild.id)
            if winner_councillor:
                await self.db_helper.update_councillor(winner_councillor['$id'], {'is_chancellor': True})

                # Update council with new chancellor
                await self.db_helper.update_council(
                    interaction.guild.id,
                    {'current_chancellor_id': winner_councillor['$id']}
                )

                # Give chancellor role to winner
                if chancellor_role:
                    try:
                        member = interaction.guild.get_member(int(winner['discord_id']))
                        if member and chancellor_role not in member.roles:
                            await member.add_roles(chancellor_role, reason="Elected as Chancellor")
                    except Exception as e:
                        print(f"Failed to add chancellor role to {winner['discord_id']}: {e}")

            # Mark winner as elected
            await self.db_helper.update_candidate(winner['$id'], {'elected': True})

            # Update voting status
            await self.db_helper.update_voting(
                voting['$id'],
                {
                    'status': VotingStatus.PASSED.value,
                    'result_announced': True
                }
            )

            # Create results embed
            results_text = "\n".join([
                f"**{i+1}.** {c['name']} - {c.get('vote_count', 0)} votes"
                for i, c in enumerate(candidates[:10])
            ])

            role_status = ""
            if chancellor_role:
                role_status = f"\n\n✅ Chancellor role has been updated!"
            else:
                role_status = f"\n\n⚠️ No chancellor role configured. Use `/set_role` to set one."

            embed = create_embed(
                title="👑 Chancellor Election Results",
                description=(
                    f"## The Council has spoken!\n\n"
                    f"**{winner['name']}** has been elected as the new Chancellor of the Grand Council!\n\n"
                    f"### 📊 Final Results\n"
                    f"{results_text}\n\n"
                    f"**Total Votes Cast:** {len(await self.db_helper.get_votes_for_voting(voting['$id']))}"
                    f"{role_status}\n\n"
                    f"Congratulations to the new Chancellor! 👑"
                ),
                color=0xFFD700,
                timestamp=datetime_now()
            )

            embed.set_footer(text="Democracy in Action")

            # Send results
            channel_id = guild_data.get('announcement_channel_id') or guild_data.get('voting_channel_id')
            if channel_id:
                channel = interaction.guild.get_channel(int(channel_id))
                if channel:
                    await channel.send(embed=embed)

            # Log action
            await self.db_helper.log(
                guild_id=interaction.guild.id,
                log_type=LogType.ELECTION,
                action="close_chancellor_election",
                discord_id=interaction.user.id,
                details={'voting_id': voting['$id'], 'winner': winner['name']}
            )

            await interaction.response.send_message(
                create_success_message(
                    f"Chancellor election closed! **{winner['name']}** is the new Chancellor."
                    + (f"\n✅ Role updated!" if chancellor_role else f"\n⚠️ No chancellor role set.")
                ),
                ephemeral=True
            )

        except Exception as e:
            await handle_interaction_error(interaction, e)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Elections(bot))
