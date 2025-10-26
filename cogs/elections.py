"""
Elections Commands Cog
Handles council elections and chancellor elections
"""
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
from datetime import datetime

from utils.database import DatabaseHelper
from utils.permissions import check_president, check_admin, can_register_to_vote, can_run_for_councillor
from utils.errors import handle_interaction_error, AlreadyExistsError, NotFoundError, InvalidInputError
from utils.formatting import (
    create_success_message, create_error_message, create_embed,
    format_timestamp, format_bold
)
from utils.helpers import datetime_now, convert_datetime_from_str, generate_keycap_emoji
from utils.enums import VotingType, VotingStatus, LogType


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

    @discord.ui.button(label="Run for Councillor", style=discord.ButtonStyle.blurple, emoji="🏃")
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


class Elections(commands.Cog):
    """Election management commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_helper: DatabaseHelper = bot.db_helper

    @app_commands.command(name='announce_election', description="[President] Announce a council election")
    @app_commands.describe(
        start_date="Start date (format: DD.MM.YYYY HH:MM)",
        end_date="End date (format: DD.MM.YYYY HH:MM)",
        channel="Channel to post announcement (optional)",
        ping_everyone="Whether to ping @everyone"
    )
    async def announce_election(
        self,
        interaction: discord.Interaction,
        start_date: str,
        end_date: str,
        channel: Optional[discord.TextChannel] = None,
        ping_everyone: bool = False
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
                    f"### 📅 Election Period\n"
                    f"**Registration & Campaigning:** {format_timestamp(start_dt, 'F')}\n"
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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Elections(bot))

