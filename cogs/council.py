"""
Council Commands Cog
Provides commands for council information and registration
"""
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone

from utils.database import DatabaseHelper
from utils.permissions import can_register_to_vote
from utils.errors import handle_interaction_error
from utils.formatting import create_embed, format_bold, create_success_message, create_error_message
from utils.helpers import datetime_now


class CouncilInfoView(discord.ui.View):
    """View with buttons for council information"""

    def __init__(self, bot: commands.Bot, db_helper: DatabaseHelper):
        super().__init__(timeout=None)
        self.bot = bot
        self.db_helper = db_helper

    @discord.ui.button(label="Learn More", style=discord.ButtonStyle.blurple, emoji="📖")
    async def learn_more(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show detailed information about the council"""
        embed = create_embed(
            title="📋 About The Grand Council",
            description=(
                "## What is the Grand Council?\n\n"
                "The Grand Council is the legislative body of this server, consisting of elected members "
                "known as Councillors (MPs). The Council has the power to:\n\n"
                "• Vote on proposed legislation and amendments\n"
                "• Propose new laws and policies\n"
                "• Hold votes of confidence\n"
                "• Impeach officials if necessary\n\n"
                "## The Chancellor\n\n"
                "The Chancellor is the head of the Council, elected by the Councillors themselves. "
                "The Chancellor has special powers including:\n\n"
                "• Creating and managing government ministries\n"
                "• Appointing ministers\n"
                "• Making official announcements\n"
                "• Guiding the direction of the Council\n\n"
                "## How to Participate\n\n"
                "• **Voting:** Register during elections to vote for Councillors\n"
                "• **Running:** Meet the requirements and run for Councillor yourself\n"
                "• **Proposing:** Once elected, propose legislation for the Council to vote on"
            ),
            color=0x4169E1
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


class Council(commands.Cog):
    """Council information and registration commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_helper: DatabaseHelper = bot.db_helper

    @app_commands.command(name="council", description="Learn about the Grand Council and how to participate")
    async def council(self, interaction: discord.Interaction):
        """Display council information"""
        try:
            guild_data = await self.db_helper.get_guild(interaction.guild.id)

            if not guild_data:
                await interaction.response.send_message(
                    create_error_message("This server is not set up yet. Ask an admin to use `/setup`."),
                    ephemeral=True
                )
                return

            # Check eligibility
            can_participate, reason = await can_register_to_vote(
                interaction.user,
                interaction.guild,
                self.db_helper
            )

            # Calculate user's stats
            joined_at = interaction.user.joined_at
            if joined_at:
                days_in_server = (datetime_now() - joined_at).days
            else:
                days_in_server = 0

            days_required = guild_data.get('days_requirement', 180)

            # Build eligibility status
            days_check = "✅" if days_in_server >= days_required else "❌"

            # Check citizen role if required
            role_check = "✅"
            role_text = ""
            if guild_data.get('citizen_role_id'):
                required_role = interaction.guild.get_role(int(guild_data['citizen_role_id']))
                if required_role:
                    role_check = "✅" if required_role in interaction.user.roles else "❌"
                    role_text = f"\n• Have the {required_role.name} role {role_check}"

            # Create main embed
            embed = create_embed(
                title="🏛️ The Grand Council",
                description=(
                    f"The Grand Council is the democratic heart of {interaction.guild.name}. "
                    "Councillors (MPs) are elected by the community to vote on legislation, "
                    "propose new laws, and shape the future of the server.\n\n"
                    "The Council is led by a Chancellor, who is elected by the Councillors themselves."
                ),
                color=0x4169E1
            )

            embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)

            # Add eligibility section
            eligibility_text = (
                f"To participate in elections, you must:\n\n"
                f"• Be a member for {days_required}+ days {days_check}\n"
                f"  (You've been here {days_in_server} days)"
                f"{role_text}\n\n"
            )

            if can_participate:
                eligibility_text += "✅ **You are eligible to participate!**"
            else:
                eligibility_text += f"❌ **Not eligible:** {reason}"

            embed.add_field(name="📋 Eligibility Requirements", value=eligibility_text, inline=False)

            # Add current stats
            councillors = await self.db_helper.list_councillors(interaction.guild.id)
            council_data = await self.db_helper.get_council(interaction.guild.id)

            stats_text = (
                f"• Current Councillors: {len(councillors)}/{guild_data.get('max_councillors', 9)}\n"
                f"• Chancellor: {'Elected' if council_data and council_data.get('current_chancellor_id') else 'Not elected yet'}"
            )

            embed.add_field(name="📊 Current Status", value=stats_text, inline=False)

            embed.set_footer(text="Use the button below to learn more about how the Council works")

            view = CouncilInfoView(self.bot, self.db_helper)

            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            await handle_interaction_error(interaction, e)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Council(bot))
