"""
Chancellor Commands Cog
Provides special commands for the elected Chancellor
Includes ministry management and announcements
"""
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

from utils.database import DatabaseHelper
from utils.permissions import check_chancellor, is_admin
from utils.errors import handle_interaction_error, NotFoundError, AlreadyExistsError
from utils.formatting import (
    create_success_message, create_error_message, create_embed,
    format_heading, format_bold, format_timestamp
)
from utils.helpers import datetime_now
from utils.enums import LogType, LogSeverity


class Chancellor(commands.Cog):
    """Chancellor-only commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_helper: DatabaseHelper = bot.db_helper

    @app_commands.command(name="create_ministry", description="[Chancellor] Create a new ministry")
    @app_commands.describe(
        name="Name of the ministry",
        description="Description of the ministry's purpose",
        minister="Discord member to assign as minister (optional)"
    )
    async def create_ministry(
        self,
        interaction: discord.Interaction,
        name: str,
        description: str,
        minister: Optional[discord.Member] = None
    ):
        """Create a new ministry"""
        try:
            await check_chancellor(interaction.user, interaction.guild, self.db_helper)

            # Check if ministry with same name exists
            existing_ministries = await self.db_helper.list_ministries(interaction.guild.id)
            for ministry in existing_ministries:
                if ministry['name'].lower() == name.lower():
                    raise AlreadyExistsError(f"A ministry named '{name}' already exists.")

            # Create ministry
            ministry_data = await self.db_helper.create_ministry(
                name=name,
                description=description,
                guild_id=interaction.guild.id,
                created_by=interaction.user.id,
                minister_discord_id=minister.id if minister else None
            )

            # Log action
            await self.db_helper.log(
                guild_id=interaction.guild.id,
                log_type=LogType.CHANCELLOR_ACTION,
                action="create_ministry",
                discord_id=interaction.user.id,
                details={'ministry_id': ministry_data['$id'], 'name': name}
            )

            embed = create_embed(
                title="🏛️ Ministry Created",
                description=(
                    f"**{name}** has been established!\n\n"
                    f"**Description:** {description}\n"
                ),
                color=0xFFD700
            )

            if minister:
                embed.add_field(name="👤 Minister", value=minister.mention, inline=False)
            else:
                embed.add_field(name="👤 Minister", value="*Not assigned*", inline=False)

            embed.set_footer(text=f"Created by {interaction.user.name}")

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await handle_interaction_error(interaction, e)

    @app_commands.command(name="assign_minister", description="[Chancellor] Assign a minister to a ministry")
    @app_commands.describe(
        ministry_name="Name of the ministry",
        minister="Discord member to assign as minister"
    )
    async def assign_minister(
        self,
        interaction: discord.Interaction,
        ministry_name: str,
        minister: discord.Member
    ):
        """Assign a minister to a ministry"""
        try:
            await check_chancellor(interaction.user, interaction.guild, self.db_helper)

            # Find ministry
            ministries = await self.db_helper.list_ministries(interaction.guild.id)
            ministry = None
            for m in ministries:
                if m['name'].lower() == ministry_name.lower():
                    ministry = m
                    break

            if not ministry:
                raise NotFoundError(f"Ministry '{ministry_name}' not found.")

            # Update ministry
            await self.db_helper.update_ministry(
                ministry['$id'],
                {'minister_discord_id': str(minister.id)}
            )

            # Log action
            await self.db_helper.log(
                guild_id=interaction.guild.id,
                log_type=LogType.CHANCELLOR_ACTION,
                action="assign_minister",
                discord_id=interaction.user.id,
                details={'ministry_id': ministry['$id'], 'minister_id': str(minister.id)}
            )

            await interaction.response.send_message(
                create_success_message(
                    f"{minister.mention} has been assigned as Minister of {ministry['name']}"
                )
            )

        except Exception as e:
            await handle_interaction_error(interaction, e)

    @app_commands.command(name="remove_ministry", description="[Chancellor] Remove a ministry")
    @app_commands.describe(ministry_name="Name of the ministry to remove")
    async def remove_ministry(
        self,
        interaction: discord.Interaction,
        ministry_name: str
    ):
        """Remove a ministry"""
        try:
            await check_chancellor(interaction.user, interaction.guild, self.db_helper)

            # Find ministry
            ministries = await self.db_helper.list_ministries(interaction.guild.id)
            ministry = None
            for m in ministries:
                if m['name'].lower() == ministry_name.lower():
                    ministry = m
                    break

            if not ministry:
                raise NotFoundError(f"Ministry '{ministry_name}' not found.")

            # Deactivate ministry instead of deleting
            await self.db_helper.update_ministry(ministry['$id'], {'active': False})

            # Log action
            await self.db_helper.log(
                guild_id=interaction.guild.id,
                log_type=LogType.CHANCELLOR_ACTION,
                action="remove_ministry",
                discord_id=interaction.user.id,
                details={'ministry_id': ministry['$id'], 'name': ministry_name}
            )

            await interaction.response.send_message(
                create_success_message(f"Ministry '{ministry_name}' has been removed.")
            )

        except Exception as e:
            await handle_interaction_error(interaction, e)

    @app_commands.command(name="list_ministries", description="[Chancellor] List all ministries")
    async def list_ministries(self, interaction: discord.Interaction):
        """List all active ministries"""
        try:
            await check_chancellor(interaction.user, interaction.guild, self.db_helper)

            ministries = await self.db_helper.list_ministries(interaction.guild.id)

            if not ministries:
                await interaction.response.send_message(
                    "No ministries have been created yet.",
                    ephemeral=True
                )
                return

            embed = create_embed(
                title="🏛️ Government Ministries",
                description=f"Active ministries in {interaction.guild.name}",
                color=0xFFD700
            )

            for ministry in ministries:
                minister_id = ministry.get('minister_discord_id')
                minister_text = "Not assigned"

                if minister_id:
                    minister = interaction.guild.get_member(int(minister_id))
                    if minister:
                        minister_text = minister.mention

                embed.add_field(
                    name=f"📋 {ministry['name']}",
                    value=(
                        f"{ministry.get('description', 'No description')}\n"
                        f"**Minister:** {minister_text}"
                    ),
                    inline=False
                )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await handle_interaction_error(interaction, e)

    @app_commands.command(name="announce", description="[Chancellor] Make an official announcement")
    @app_commands.describe(
        title="Announcement title",
        message="Announcement message",
        ping_everyone="Whether to ping @everyone (use sparingly)"
    )
    async def announce(
        self,
        interaction: discord.Interaction,
        title: str,
        message: str,
        ping_everyone: bool = False
    ):
        """Make an official announcement"""
        try:
            await check_chancellor(interaction.user, interaction.guild, self.db_helper)

            guild_data = await self.db_helper.get_guild(interaction.guild.id)

            # Determine announcement channel
            channel_id = guild_data.get('announcement_channel_id') or guild_data.get('voting_channel_id')

            if not channel_id:
                await interaction.response.send_message(
                    create_error_message(
                        "No announcement channel configured. Ask an admin to set one with `/set_channel`."
                    ),
                    ephemeral=True
                )
                return

            channel = interaction.guild.get_channel(int(channel_id))
            if not channel:
                await interaction.response.send_message(
                    create_error_message("Announcement channel not found."),
                    ephemeral=True
                )
                return

            # Create announcement embed
            embed = create_embed(
                title=f"📢 {title}",
                description=message,
                color=0xFFD700,
                timestamp=datetime_now()
            )

            embed.set_author(
                name=f"Chancellor {interaction.user.name}",
                icon_url=interaction.user.display_avatar.url
            )

            embed.set_footer(text="Official Government Announcement")

            # Send announcement
            content = "@everyone" if ping_everyone else None
            await channel.send(content=content, embed=embed)

            # Log action
            await self.db_helper.log(
                guild_id=interaction.guild.id,
                log_type=LogType.CHANCELLOR_ACTION,
                action="announcement",
                discord_id=interaction.user.id,
                details={'title': title, 'pinged_everyone': ping_everyone}
            )

            await interaction.response.send_message(
                create_success_message(f"Announcement posted in {channel.mention}"),
                ephemeral=True
            )

        except Exception as e:
            await handle_interaction_error(interaction, e)

    @app_commands.command(name="appoint_role", description="[Chancellor] Request role assignment for a ministry")
    @app_commands.describe(
        ministry_name="Name of the ministry",
        role="Discord role to associate with this ministry"
    )
    async def appoint_role(
        self,
        interaction: discord.Interaction,
        ministry_name: str,
        role: discord.Role
    ):
        """Associate a Discord role with a ministry"""
        try:
            await check_chancellor(interaction.user, interaction.guild, self.db_helper)

            # Find ministry
            ministries = await self.db_helper.list_ministries(interaction.guild.id)
            ministry = None
            for m in ministries:
                if m['name'].lower() == ministry_name.lower():
                    ministry = m
                    break

            if not ministry:
                raise NotFoundError(f"Ministry '{ministry_name}' not found.")

            # Get current role_ids
            role_ids = ministry.get('role_ids', [])
            if not isinstance(role_ids, list):
                role_ids = []

            # Add role if not already present
            if str(role.id) not in role_ids:
                role_ids.append(str(role.id))

                await self.db_helper.update_ministry(
                    ministry['$id'],
                    {'role_ids': role_ids}
                )

                # Log action
                await self.db_helper.log(
                    guild_id=interaction.guild.id,
                    log_type=LogType.CHANCELLOR_ACTION,
                    action="appoint_role",
                    discord_id=interaction.user.id,
                    details={'ministry_id': ministry['$id'], 'role_id': str(role.id)}
                )

                await interaction.response.send_message(
                    create_success_message(
                        f"Role {role.mention} has been associated with {ministry['name']}"
                    )
                )
            else:
                await interaction.response.send_message(
                    create_error_message(f"Role {role.mention} is already associated with this ministry."),
                    ephemeral=True
                )

        except Exception as e:
            await handle_interaction_error(interaction, e)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Chancellor(bot))

