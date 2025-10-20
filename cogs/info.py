"""
Information Commands Cog
Provides commands to display information about the council and democracy system
"""
import discord
from discord.ext import commands
from discord import app_commands

from utils.database import DatabaseHelper
from utils.errors import handle_interaction_error
from utils.formatting import create_embed, format_bold, create_error_message, format_timestamp
from utils.helpers import datetime_now


class Information(commands.Cog):
    """Information display commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_helper: DatabaseHelper = bot.db_helper

    @app_commands.command(name="info", description="View current council information and members")
    async def info(self, interaction: discord.Interaction):
        """Display current council information"""
        try:
            guild_data = await self.db_helper.get_guild(interaction.guild.id)

            if not guild_data:
                await interaction.response.send_message(
                    create_error_message("This server is not set up yet. Ask an admin to use `/setup`."),
                    ephemeral=True
                )
                return

            # Get council data
            council_data = await self.db_helper.get_council(interaction.guild.id)
            councillors = await self.db_helper.list_councillors(interaction.guild.id)

            # Create main embed
            embed = create_embed(
                title="🏛️ Council Information",
                description=(
                    f"**{interaction.guild.name}**\n\n"
                    "The Grand Council is the democratic legislative body of this server. "
                    "Councillors vote on proposals, create legislation, and shape server policy."
                ),
                color=0x4169E1
            )

            embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)

            # Chancellor section
            chancellor_text = "Not elected yet"
            if council_data and council_data.get('current_chancellor_id'):
                chancellor = interaction.guild.get_member(int(council_data['current_chancellor_id']))
                if chancellor:
                    chancellor_text = f"{chancellor.mention}\n{chancellor.name}"

            embed.add_field(name="👑 Chancellor", value=chancellor_text, inline=True)

            # Council size
            max_councillors = guild_data.get('max_councillors', 9)
            embed.add_field(
                name="📊 Council Size",
                value=f"{len(councillors)}/{max_councillors} seats filled",
                inline=True
            )

            # Election status
            election_status = "No election in progress"
            if council_data and council_data.get('election_in_progress'):
                election_status = "🗳️ Election in progress!"

            embed.add_field(name="📅 Status", value=election_status, inline=True)

            # List councillors
            if councillors:
                # Sort by joined_at
                councillors.sort(key=lambda x: x.get('joined_at', ''), reverse=False)

                councillor_list = []
                for i, councillor in enumerate(councillors[:20], 1):  # Show max 20
                    member = interaction.guild.get_member(int(councillor['discord_id']))
                    if member:
                        is_chancellor = councillor.get('is_chancellor', False)
                        emoji = "👑" if is_chancellor else "🔹"
                        councillor_list.append(f"{emoji} {member.mention}")

                if councillor_list:
                    embed.add_field(
                        name=f"👥 Current Councillors ({len(councillor_list)})",
                        value="\n".join(councillor_list),
                        inline=False
                    )

                if len(councillors) > 20:
                    embed.add_field(
                        name="",
                        value=f"*... and {len(councillors) - 20} more*",
                        inline=False
                    )
            else:
                embed.add_field(
                    name="👥 Current Councillors",
                    value="No councillors elected yet",
                    inline=False
                )

            # Ministries
            ministries = await self.db_helper.list_ministries(interaction.guild.id)
            if ministries:
                ministry_text = []
                for ministry in ministries[:5]:  # Show max 5
                    minister_id = ministry.get('minister_discord_id')
                    if minister_id:
                        minister = interaction.guild.get_member(int(minister_id))
                        minister_name = minister.name if minister else "Unknown"
                    else:
                        minister_name = "*Not assigned*"

                    ministry_text.append(f"🏛️ **{ministry['name']}** - {minister_name}")

                embed.add_field(
                    name="🏛️ Government Ministries",
                    value="\n".join(ministry_text),
                    inline=False
                )

            embed.set_footer(text=f"Use /council to learn how to participate • {datetime_now().strftime('%B %Y')}")

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await handle_interaction_error(interaction, e)

    @app_commands.command(name="voting_info", description="View information about active votings")
    async def voting_info(self, interaction: discord.Interaction):
        """Display information about active votings"""
        try:
            guild_data = await self.db_helper.get_guild(interaction.guild.id)

            if not guild_data:
                await interaction.response.send_message(
                    create_error_message("This server is not set up yet."),
                    ephemeral=True
                )
                return

            # Get active votings
            active_votings = await self.db_helper.list_active_votings(interaction.guild.id)

            embed = create_embed(
                title="🗳️ Active Votings",
                description=f"Current voting proposals in {interaction.guild.name}",
                color=0x4169E1
            )

            if not active_votings:
                embed.description = "There are currently no active votings."
            else:
                for voting in active_votings[:10]:  # Show max 10
                    from utils.enums import VotingType, VOTING_TYPE_CONFIG
                    from datetime import datetime

                    voting_type = VotingType(voting['type'])
                    config = VOTING_TYPE_CONFIG.get(voting_type, {})

                    # Get vote counts
                    votes = await self.db_helper.get_votes_for_voting(voting['$id'])
                    yes_votes = sum(1 for v in votes if v.get('stance', False))
                    no_votes = len(votes) - yes_votes

                    # Parse end date
                    end_date = datetime.fromisoformat(voting['voting_end'].replace('Z', '+00:00'))

                    field_value = (
                        f"{config.get('emoji', '🗳️')} **Type:** {config.get('text', voting['type'])}\n"
                        f"📊 **Votes:** {yes_votes} For, {no_votes} Against\n"
                        f"⏰ **Ends:** {format_timestamp(end_date, 'R')}\n"
                    )

                    if voting.get('description'):
                        desc = voting['description'][:100]
                        if len(voting['description']) > 100:
                            desc += "..."
                        field_value += f"📝 {desc}\n"

                    embed.add_field(
                        name=voting['title'],
                        value=field_value,
                        inline=False
                    )

            embed.set_footer(text="Check the voting channel for full details and to cast your vote")

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await handle_interaction_error(interaction, e)

    @app_commands.command(name="help", description="Display help information and available commands")
    async def help_command(self, interaction: discord.Interaction):
        """Display help information"""
        try:
            from utils.permissions import is_admin, is_eligible
            from utils.enums import RoleType

            # Check user roles
            is_user_admin = await is_admin(interaction.user)
            is_councillor = await is_eligible(interaction.user, interaction.guild, RoleType.COUNCILLOR, self.db_helper)
            is_chancellor = await is_eligible(interaction.user, interaction.guild, RoleType.CHANCELLOR, self.db_helper)

            embed = create_embed(
                title="📚 Councillor Bot - Help",
                description=(
                    "Welcome to the Councillor Bot! This bot manages democratic processes in your server.\n\n"
                    "Here are the commands available to you:"
                ),
                color=0x4169E1
            )

            # General commands (everyone)
            general_commands = [
                "`/council` - Learn about the Grand Council and eligibility",
                "`/info` - View current council members and information",
                "`/voting_info` - See active votings and proposals",
                "`/help` - Display this help message"
            ]

            embed.add_field(
                name="📋 General Commands",
                value="\n".join(general_commands),
                inline=False
            )

            # Councillor commands
            if is_councillor or is_user_admin:
                councillor_commands = [
                    "`/propose` - Create a new proposal for voting",
                ]

                embed.add_field(
                    name="⚖️ Councillor Commands",
                    value="\n".join(councillor_commands),
                    inline=False
                )

            # Chancellor commands
            if is_chancellor or is_user_admin:
                chancellor_commands = [
                    "`/create_ministry` - Create a new government ministry",
                    "`/assign_minister` - Assign a minister to a ministry",
                    "`/list_ministries` - View all ministries",
                    "`/announce` - Make an official announcement",
                    "`/appoint_role` - Associate a role with a ministry",
                    "`/remove_ministry` - Remove a ministry"
                ]

                embed.add_field(
                    name="👑 Chancellor Commands",
                    value="\n".join(chancellor_commands),
                    inline=False
                )

            # Admin commands
            if is_user_admin:
                admin_commands = [
                    "`/setup` - Initial bot setup",
                    "`/config` - View configuration",
                    "`/set_role` - Configure roles",
                    "`/set_channel` - Configure channels",
                    "`/set_requirement` - Set participation requirements",
                    "`/toggle_bot` - Enable/disable the bot",
                    "`/elections` - Manage elections"
                ]

                embed.add_field(
                    name="🔧 Admin Commands",
                    value="\n".join(admin_commands),
                    inline=False
                )

            embed.set_footer(text="For detailed help on a specific command, use /command_name")

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await handle_interaction_error(interaction, e)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Information(bot))
