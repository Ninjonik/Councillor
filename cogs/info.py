"""
Info Commands Cog
Provides help and information commands
"""
import discord
from discord import app_commands
from discord.ext import commands

from utils.database import DatabaseHelper
from utils.formatting import create_embed
from utils.errors import handle_interaction_error


class Info(commands.Cog):
    """Information and help commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_helper: DatabaseHelper = bot.db_helper

    @app_commands.command(name="help", description="Show all available commands and how to use the bot")
    async def help(self, interaction: discord.Interaction):
        """Display help information"""
        try:
            embed = create_embed(
                title="📚 Councillor Bot - Command Reference",
                description=(
                    "Welcome to the Councillor Bot! This bot helps you run a democratic server "
                    "with elections, councils, and voting on proposals.\n\n"
                    "Commands are organized by role. Use the buttons below to see commands for each role."
                ),
                color=0x4169E1
            )

            # General Commands
            embed.add_field(
                name="🌍 General Commands",
                value=(
                    "`/council` - Learn about the Grand Council and check your eligibility\n"
                    "`/help` - Show this help message"
                ),
                inline=False
            )

            # Admin Commands
            embed.add_field(
                name="⚙️ Admin Commands",
                value=(
                    "`/setup` - Initial setup for the bot in this server\n"
                    "`/config` - View current configuration\n"
                    "`/set_role` - Configure roles (Councillor, Chancellor, etc.)\n"
                    "`/set_channel` - Set voting and announcement channels\n"
                    "`/set_requirement` - Set participation requirements\n"
                    "`/toggle_bot` - Enable or disable the bot"
                ),
                inline=False
            )

            # President Commands
            embed.add_field(
                name="🎖️ President Commands",
                value=(
                    "`/announce_election` - Announce a new council election\n"
                    "`/start_voting` - Start the voting phase of an election\n"
                    "`/close_election` - Close election and elect winners"
                ),
                inline=False
            )

            # Councillor Commands
            embed.add_field(
                name="🏛️ Councillor Commands",
                value=(
                    "`/propose` - Create a proposal for the Council to vote on\n"
                    "Click voting buttons on proposals to vote"
                ),
                inline=False
            )

            # Chancellor Commands
            embed.add_field(
                name="👑 Chancellor Commands",
                value=(
                    "`/create_ministry` - Create a new ministry\n"
                    "`/assign_minister` - Assign a minister to a ministry\n"
                    "`/remove_ministry` - Remove a ministry\n"
                    "`/list_ministries` - List all ministries\n"
                    "`/announce` - Make an official announcement\n"
                    "`/appoint_role` - Associate a Discord role with a ministry"
                ),
                inline=False
            )

            embed.add_field(
                name="🗳️ Election Process",
                value=(
                    "1. **President announces election** with `/announce_election`\n"
                    "2. **Citizens register** to vote and **candidates register** using buttons\n"
                    "3. **President starts voting** with `/start_voting`\n"
                    "4. **Registered voters cast votes** for their favorite candidates\n"
                    "5. **President closes election** with `/close_election` to finalize results"
                ),
                inline=False
            )

            embed.set_footer(text="For more help, contact your server administrator")

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await handle_interaction_error(interaction, e)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Info(bot))

