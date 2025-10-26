"""
Admin Commands Cog
Provides administrative commands for bot configuration
Only accessible to the configured admin user
"""
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

import config
from utils.database import DatabaseHelper
from utils.permissions import is_admin, check_admin
from utils.errors import handle_interaction_error
from utils.formatting import (
    create_success_message, create_error_message, create_embed,
    format_heading, format_bold
)


class Admin(commands.Cog):
    """Admin commands for bot configuration"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_helper: DatabaseHelper = bot.db_helper

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if user is admin before allowing any command"""
        if not await is_admin(interaction.user):
            await interaction.response.send_message(
                create_error_message("You must be an admin to use this command."),
                ephemeral=True
            )
            return False
        return True

    @app_commands.command(name="setup", description="[Admin] Initial setup for the bot in this server")
    async def setup(self, interaction: discord.Interaction):
        """Initial setup wizard for the bot"""
        try:
            await check_admin(interaction.user)

            # Check if guild exists
            guild_data = await self.db_helper.get_guild(interaction.guild.id)

            if guild_data:
                await interaction.response.send_message(
                    create_error_message("This server is already set up. Use `/config` to modify settings."),
                    ephemeral=True
                )
                return

            # Create guild
            await self.db_helper.create_guild(
                interaction.guild.id,
                interaction.guild.name,
                interaction.guild.description or ""
            )

            embed = create_embed(
                title="✅ Setup Complete!",
                description=(
                    "The Councillor bot has been set up for this server.\n\n"
                    "## Next Steps\n"
                    "Use the following commands to configure the bot:\n\n"
                    "• `/config set_role` - Configure required roles\n"
                    "• `/config set_channel` - Set voting and announcement channels\n"
                    "• `/config set_requirement` - Set membership requirements\n"
                    "• `/config view` - View current configuration\n\n"
                    "For a list of all commands, use `/help`"
                ),
                color=0x00FF00
            )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await handle_interaction_error(interaction, e)

    @app_commands.command(name="config", description="[Admin] Configure bot settings")
    @app_commands.describe(
        action="What to do",
        setting="Setting to configure",
        value="New value for the setting"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="View Configuration", value="view"),
        app_commands.Choice(name="Set Role", value="set_role"),
        app_commands.Choice(name="Set Channel", value="set_channel"),
        app_commands.Choice(name="Set Requirement", value="set_requirement"),
    ])
    async def config(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        setting: Optional[str] = None,
        value: Optional[str] = None
    ):
        """Configure bot settings"""
        try:
            await check_admin(interaction.user)

            if action.value == "view":
                await self.show_config(interaction)
            elif action.value == "set_role":
                await interaction.response.send_message(
                    "Please use the `/set_role` command to configure roles.",
                    ephemeral=True
                )
            elif action.value == "set_channel":
                await interaction.response.send_message(
                    "Please use the `/set_channel` command to configure channels.",
                    ephemeral=True
                )
            elif action.value == "set_requirement":
                await interaction.response.send_message(
                    "Please use the `/set_requirement` command to configure requirements.",
                    ephemeral=True
                )

        except Exception as e:
            await handle_interaction_error(interaction, e)

    async def show_config(self, interaction: discord.Interaction):
        """Display current configuration"""
        guild_data = await self.db_helper.get_guild(interaction.guild.id)

        if not guild_data:
            await interaction.response.send_message(
                create_error_message("This server is not set up. Use `/setup` first."),
                ephemeral=True
            )
            return

        embed = create_embed(
            title="⚙️ Bot Configuration",
            description=f"Current settings for {interaction.guild.name}",
            color=0x4169E1
        )

        # Roles
        roles_text = ""
        role_fields = [
            ('councillor_role_id', 'Councillor'),
            ('chancellor_role_id', 'Chancellor'),
            ('minister_role_id', 'Minister'),
            ('president_role_id', 'President'),
            ('vice_president_role_id', 'Vice President'),
            ('judiciary_role_id', 'Judiciary'),
            ('citizen_role_id', 'Citizen (Required)')
        ]

        for field, label in role_fields:
            role_id = guild_data.get(field)
            if role_id:
                role = interaction.guild.get_role(int(role_id))
                roles_text += f"• {label}: {role.mention if role else 'Not Found'}\n"
            else:
                roles_text += f"• {label}: Not Set\n"

        embed.add_field(name="🎭 Roles", value=roles_text or "None configured", inline=False)

        # Channels
        channels_text = ""
        channel_fields = [
            ('voting_channel_id', 'Voting Channel'),
            ('announcement_channel_id', 'Announcement Channel')
        ]

        for field, label in channel_fields:
            channel_id = guild_data.get(field)
            if channel_id:
                channel = interaction.guild.get_channel(int(channel_id))
                channels_text += f"• {label}: {channel.mention if channel else 'Not Found'}\n"
            else:
                channels_text += f"• {label}: Not Set\n"

        embed.add_field(name="📺 Channels", value=channels_text or "None configured", inline=False)

        # Requirements
        requirements_text = (
            f"• Days Required: {guild_data.get('days_requirement', 180)} days\n"
            f"• Max Councillors: {guild_data.get('max_councillors', 9)}\n"
            f"• Bot Enabled: {'Yes' if guild_data.get('enabled', True) else 'No'}\n"
            f"• Logging Enabled: {'Yes' if guild_data.get('logging_enabled', True) else 'No'}"
        )

        embed.add_field(name="📋 Requirements", value=requirements_text, inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="set_role", description="[Admin] Set a role for the democracy system")
    @app_commands.describe(
        role_type="Type of role to set",
        role="The Discord role"
    )
    @app_commands.choices(role_type=[
        app_commands.Choice(name="Councillor", value="councillor_role_id"),
        app_commands.Choice(name="Chancellor", value="chancellor_role_id"),
        app_commands.Choice(name="Minister", value="minister_role_id"),
        app_commands.Choice(name="President", value="president_role_id"),
        app_commands.Choice(name="Vice President", value="vice_president_role_id"),
        app_commands.Choice(name="Judiciary", value="judiciary_role_id"),
        app_commands.Choice(name="Citizen (Required)", value="citizen_role_id"),
    ])
    async def set_role(
        self,
        interaction: discord.Interaction,
        role_type: app_commands.Choice[str],
        role: discord.Role
    ):
        """Set a role for the democracy system"""
        try:
            await check_admin(interaction.user)

            await self.db_helper.update_guild(
                interaction.guild.id,
                {role_type.value: str(role.id)}
            )

            await interaction.response.send_message(
                create_success_message(f"Set {role_type.name} role to {role.mention}")
            )

        except Exception as e:
            await handle_interaction_error(interaction, e)

    @app_commands.command(name="set_channel", description="[Admin] Set a channel for bot operations")
    @app_commands.describe(
        channel_type="Type of channel to set",
        channel="The Discord channel"
    )
    @app_commands.choices(channel_type=[
        app_commands.Choice(name="Voting Channel", value="voting_channel_id"),
        app_commands.Choice(name="Announcement Channel", value="announcement_channel_id"),
    ])
    async def set_channel(
        self,
        interaction: discord.Interaction,
        channel_type: app_commands.Choice[str],
        channel: discord.TextChannel
    ):
        """Set a channel for bot operations"""
        try:
            await check_admin(interaction.user)

            await self.db_helper.update_guild(
                interaction.guild.id,
                {channel_type.value: str(channel.id)}
            )

            await interaction.response.send_message(
                create_success_message(f"Set {channel_type.name} to {channel.mention}")
            )

        except Exception as e:
            await handle_interaction_error(interaction, e)

    @app_commands.command(name="set_requirement", description="[Admin] Set requirements for participation")
    @app_commands.describe(
        days="Minimum days in server to participate",
        max_councillors="Maximum number of councillors allowed"
    )
    async def set_requirement(
        self,
        interaction: discord.Interaction,
        days: Optional[int] = None,
        max_councillors: Optional[int] = None
    ):
        """Set requirements for participation"""
        try:
            await check_admin(interaction.user)

            if days is None and max_councillors is None:
                await interaction.response.send_message(
                    create_error_message("Please provide at least one value to update."),
                    ephemeral=True
                )
                return

            update_data = {}
            messages = []

            if days is not None:
                if days < 0:
                    await interaction.response.send_message(
                        create_error_message("Days must be a positive number."),
                        ephemeral=True
                    )
                    return
                update_data['days_requirement'] = days
                messages.append(f"Days requirement set to {days} days")

            if max_councillors is not None:
                if max_councillors < 1:
                    await interaction.response.send_message(
                        create_error_message("Max councillors must be at least 1."),
                        ephemeral=True
                    )
                    return
                update_data['max_councillors'] = max_councillors
                messages.append(f"Max councillors set to {max_councillors}")

            await self.db_helper.update_guild(interaction.guild.id, update_data)

            await interaction.response.send_message(
                create_success_message("\n".join(messages))
            )

        except Exception as e:
            await handle_interaction_error(interaction, e)

    @app_commands.command(name="toggle_bot", description="[Admin] Enable or disable the bot for this server")
    @app_commands.describe(enabled="Whether the bot should be enabled")
    async def toggle_bot(self, interaction: discord.Interaction, enabled: bool):
        """Enable or disable the bot"""
        try:
            await check_admin(interaction.user)

            await self.db_helper.update_guild(
                interaction.guild.id,
                {'enabled': enabled}
            )

            status = "enabled" if enabled else "disabled"
            await interaction.response.send_message(
                create_success_message(f"Bot has been {status} for this server.")
            )

        except Exception as e:
            await handle_interaction_error(interaction, e)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))

