"""
Propose Commands Cog
Allows councillors to create proposals for voting
"""
import discord
from discord import app_commands
from discord.ext import commands

from utils.database import DatabaseHelper
from utils.permissions import check_councillor
from utils.errors import handle_interaction_error
from utils.formatting import create_success_message, create_embed, format_timestamp, create_error_message
from utils.helpers import calculate_voting_end_date
from utils.enums import VotingType, VotingStatus, VOTING_TYPE_CONFIG


class VotingView(discord.ui.View):
    """View with voting buttons"""

    def __init__(self, bot: commands.Bot, db_helper: DatabaseHelper):
        super().__init__(timeout=None)
        self.bot = bot
        self.db_helper = db_helper

    @discord.ui.button(label="Vote For", style=discord.ButtonStyle.green, emoji="✅", custom_id="vote_for")
    async def vote_for(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Vote in favor of the proposal"""
        await self.cast_vote(interaction, True)

    @discord.ui.button(label="Vote Against", style=discord.ButtonStyle.red, emoji="❌", custom_id="vote_against")
    async def vote_against(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Vote against the proposal"""
        await self.cast_vote(interaction, False)

    async def cast_vote(self, interaction: discord.Interaction, stance: bool):
        """Handle vote casting"""
        try:
            from utils.permissions import is_eligible
            from utils.enums import RoleType, LogType

            # Check if user is a councillor
            if not await is_eligible(interaction.user, interaction.guild, RoleType.COUNCILLOR, self.db_helper):
                await interaction.response.send_message(
                    create_error_message("Only Councillors can vote on proposals."),
                    ephemeral=True
                )
                return

            # Get voting ID from message
            voting_id = str(interaction.message.id)

            # Get councillor data
            councillor = await self.db_helper.get_councillor(interaction.user.id, interaction.guild.id)
            if not councillor:
                await interaction.response.send_message(
                    create_error_message("Your councillor record could not be found."),
                    ephemeral=True
                )
                return

            # Check if already voted
            has_voted = await self.db_helper.has_voted(voting_id, councillor_id=councillor['$id'])
            if has_voted:
                await interaction.response.send_message(
                    create_error_message("You have already voted on this proposal."),
                    ephemeral=True
                )
                return

            # Cast vote
            await self.db_helper.cast_vote(
                voting_id=voting_id,
                stance=stance,
                councillor_id=councillor['$id']
            )

            # Log the vote
            await self.db_helper.log(
                guild_id=interaction.guild.id,
                log_type=LogType.VOTE,
                action="cast_vote",
                discord_id=interaction.user.id,
                details={'voting_id': voting_id, 'stance': stance}
            )

            vote_text = "✅ **For**" if stance else "❌ **Against**"
            await interaction.response.send_message(
                create_success_message(f"Your vote ({vote_text}) has been recorded!"),
                ephemeral=True
            )

        except Exception as e:
            await handle_interaction_error(interaction, e)


class Propose(commands.Cog):
    """Proposal creation commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_helper: DatabaseHelper = bot.db_helper

    @app_commands.command(name='propose', description="[Councillor] Create a proposal for the Council to vote on")
    @app_commands.describe(
        title="Title of the proposal",
        description="Detailed description of what is being proposed",
        voting_type="Type of proposal"
    )
    @app_commands.choices(voting_type=[
        app_commands.Choice(name="⚖️ Legislation", value=VotingType.LEGISLATION.value),
        app_commands.Choice(name="🔵 Amendment", value=VotingType.AMENDMENT.value),
        app_commands.Choice(name="📜 Impeachment", value=VotingType.IMPEACHMENT.value),
        app_commands.Choice(name="⚠️ Confidence Vote", value=VotingType.CONFIDENCE_VOTE.value),
        app_commands.Choice(name="🛑 Decree", value=VotingType.DECREE.value),
        app_commands.Choice(name="🗳️ Other", value=VotingType.OTHER.value),
    ])
    async def propose(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        voting_type: app_commands.Choice[str]
    ):
        """Create a new proposal for voting"""
        try:
            await check_councillor(interaction.user, interaction.guild, self.db_helper)

            guild_data = await self.db_helper.get_guild(interaction.guild.id)
            if not guild_data:
                await interaction.response.send_message(
                    create_error_message("This server is not set up yet."),
                    ephemeral=True
                )
                return

            # Check if voting channel is configured
            if not guild_data.get('voting_channel_id'):
                await interaction.response.send_message(
                    create_error_message("No voting channel configured. Ask an admin to set one with `/set_channel`."),
                    ephemeral=True
                )
                return

            voting_channel = interaction.guild.get_channel(int(guild_data['voting_channel_id']))
            if not voting_channel:
                await interaction.response.send_message(
                    create_error_message("Voting channel not found."),
                    ephemeral=True
                )
                return

            # Get councillor data
            councillor = await self.db_helper.get_councillor(interaction.user.id, interaction.guild.id)
            if not councillor:
                await interaction.response.send_message(
                    create_error_message("Your councillor record could not be found."),
                    ephemeral=True
                )
                return

            # Get voting type configuration
            vtype = VotingType(voting_type.value)
            vtype_config = VOTING_TYPE_CONFIG[vtype]

            # Calculate voting end date
            voting_end = calculate_voting_end_date(vtype_config['voting_days'], after_noon=True)

            # Create embed for the proposal
            embed = create_embed(
                title=title,
                description=description,
                color=vtype_config['color']
            )

            embed.set_author(
                name=f"{interaction.user.name}",
                icon_url=interaction.user.display_avatar.url
            )

            embed.add_field(
                name="📋 Type",
                value=f"{vtype_config['emoji']} {vtype_config['text']}",
                inline=True
            )

            embed.add_field(
                name="📊 Required",
                value=f">{vtype_config['required_percentage'] * 100:.0f}% approval",
                inline=True
            )

            embed.add_field(
                name="⏰ Voting Ends",
                value=format_timestamp(voting_end, 'R'),
                inline=True
            )

            embed.set_footer(text=f"Vote using the buttons below • ID: pending")

            # Send proposal to voting channel
            view = VotingView(self.bot, self.db_helper)

            # Mention councillors if role is configured
            content = None
            if guild_data.get('councillor_role_id'):
                content = f"<@&{guild_data['councillor_role_id']}>"

            message = await voting_channel.send(content=content, embed=embed, view=view)

            # Create voting record
            voting = await self.db_helper.create_voting(
                voting_type=vtype,
                title=title,
                description=description,
                guild_id=interaction.guild.id,
                voting_end=voting_end,
                proposer_id=councillor['$id'],
                status=VotingStatus.VOTING,
                message_id=str(message.id),
                required_percentage=vtype_config['required_percentage']
            )

            # Update embed with voting ID
            embed.set_footer(text=f"Vote using the buttons below • ID: {voting['$id']}")
            await message.edit(embed=embed)

            # Log the action
            from utils.enums import LogType
            await self.db_helper.log(
                guild_id=interaction.guild.id,
                log_type=LogType.COMMAND,
                action="create_proposal",
                discord_id=interaction.user.id,
                details={'voting_id': voting['$id'], 'type': voting_type.value}
            )

            await interaction.response.send_message(
                create_success_message(
                    f"Your proposal has been posted in {voting_channel.mention}!\n"
                    f"Voting ends {format_timestamp(voting_end, 'R')}"
                ),
                ephemeral=True
            )

        except Exception as e:
            await handle_interaction_error(interaction, e)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Propose(bot))
