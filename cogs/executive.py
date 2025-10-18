import discord
from discord import app_commands
from discord.ext import commands
from utils import is_chancellor, get_all_ministries, create_ministry, update_ministry, delete_ministry, is_president, is_vice_president, is_councillor, has_role
from embeds import create_success_embed, create_error_embed, create_ministry_list_embed
import config
from appwrite.id import ID

# Admin user ID - has wildcard permissions
ADMIN_USER_ID = 231105080961531905

async def is_admin_or_chancellor(user: discord.Member, db_client) -> bool:
    """Check if user is admin or chancellor"""
    if user.id == ADMIN_USER_ID:
        return True
    return await has_role(user, "chancellor", db_client)

class Executive(commands.Cog):
    """Chancellor executive commands and ministry management"""

    def __init__(self, bot):
        self.bot = bot

    # Ministry Management Commands

    @app_commands.command(name="ministries", description="View all ministries and their leadership")
    @app_commands.guild_only()
    async def ministries(self, interaction: discord.Interaction):
        """View all ministries"""
        await interaction.response.defer()

        try:
            ministries = await get_all_ministries(self.bot.db, interaction.guild.id)
            embed = create_ministry_list_embed(interaction.guild, ministries)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(
                embed=create_error_embed("Error", f"Failed to fetch ministries: {str(e)}"),
                ephemeral=True
            )

    @app_commands.command(name="create_ministry", description="[Chancellor] Create a new ministry")
    @app_commands.describe(
        name="Name of the ministry",
        role="Discord role for this ministry (optional)",
        deputy_role="Discord role for deputy minister (optional)"
    )
    @app_commands.guild_only()
    async def create_ministry_cmd(
        self,
        interaction: discord.Interaction,
        name: str,
        role: discord.Role = None,
        deputy_role: discord.Role = None
    ):
        """Create a new ministry"""
        if not await is_admin_or_chancellor(interaction.user, self.bot.db):
            return await interaction.response.send_message(
                embed=create_error_embed("Permission Denied", "Only the Chancellor can create ministries."),
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        try:
            ministry = await create_ministry(
                self.bot.db,
                interaction.guild.id,
                name,
                str(role.id) if role else None,
                str(deputy_role.id) if deputy_role else None
            )

            if ministry:
                await interaction.followup.send(
                    embed=create_success_embed(
                        "Ministry Created",
                        f"**{name}** has been created successfully.\n"
                        f"Role: {role.mention if role else '*Not assigned*'}\n"
                        f"Deputy Role: {deputy_role.mention if deputy_role else '*Not assigned*'}"
                    ),
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    embed=create_error_embed("Error", "Failed to create ministry."),
                    ephemeral=True
                )
        except Exception as e:
            await interaction.followup.send(
                embed=create_error_embed("Error", f"Failed to create ministry: {str(e)}"),
                ephemeral=True
            )

    @app_commands.command(name="appoint_minister", description="[Chancellor] Appoint a minister to a ministry")
    @app_commands.describe(
        ministry_name="Name of the ministry",
        member="Member to appoint as minister"
    )
    @app_commands.guild_only()
    async def appoint_minister(self, interaction: discord.Interaction, ministry_name: str, member: discord.Member):
        """Appoint a minister"""
        if not await is_admin_or_chancellor(interaction.user, self.bot.db):
            return await interaction.response.send_message(
                embed=create_error_embed("Permission Denied", "Only the Chancellor can appoint ministers."),
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        try:
            # Find the ministry
            ministries = await get_all_ministries(self.bot.db, interaction.guild.id)
            ministry = next((m for m in ministries if m['name'].lower() == ministry_name.lower()), None)

            if not ministry:
                return await interaction.followup.send(
                    embed=create_error_embed("Not Found", f"Ministry '{ministry_name}' not found."),
                    ephemeral=True
                )

            # Update ministry with new minister
            updated = await update_ministry(self.bot.db, ministry['$id'], {"minister_id": str(member.id)})

            if updated:
                # Assign role if exists
                if ministry.get('role_id'):
                    role = interaction.guild.get_role(int(ministry['role_id']))
                    if role:
                        await member.add_roles(role, reason=f"Appointed as Minister of {ministry['name']}")

                await interaction.followup.send(
                    embed=create_success_embed(
                        "Minister Appointed",
                        f"{member.mention} has been appointed as **Minister of {ministry['name']}**."
                    ),
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    embed=create_error_embed("Error", "Failed to appoint minister."),
                    ephemeral=True
                )
        except Exception as e:
            await interaction.followup.send(
                embed=create_error_embed("Error", f"Failed to appoint minister: {str(e)}"),
                ephemeral=True
            )

    @app_commands.command(name="appoint_deputy", description="[Chancellor] Appoint a deputy minister to a ministry")
    @app_commands.describe(
        ministry_name="Name of the ministry",
        member="Member to appoint as deputy minister"
    )
    @app_commands.guild_only()
    async def appoint_deputy(self, interaction: discord.Interaction, ministry_name: str, member: discord.Member):
        """Appoint a deputy minister"""
        if not await is_admin_or_chancellor(interaction.user, self.bot.db):
            return await interaction.response.send_message(
                embed=create_error_embed("Permission Denied", "Only the Chancellor can appoint deputy ministers."),
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        try:
            # Find the ministry
            ministries = await get_all_ministries(self.bot.db, interaction.guild.id)
            ministry = next((m for m in ministries if m['name'].lower() == ministry_name.lower()), None)

            if not ministry:
                return await interaction.followup.send(
                    embed=create_error_embed("Not Found", f"Ministry '{ministry_name}' not found."),
                    ephemeral=True
                )

            # Update ministry with new deputy
            updated = await update_ministry(self.bot.db, ministry['$id'], {"deputy_minister_id": str(member.id)})

            if updated:
                # Assign deputy role if exists
                if ministry.get('deputy_role_id'):
                    role = interaction.guild.get_role(int(ministry['deputy_role_id']))
                    if role:
                        await member.add_roles(role, reason=f"Appointed as Deputy Minister of {ministry['name']}")

                await interaction.followup.send(
                    embed=create_success_embed(
                        "Deputy Minister Appointed",
                        f"{member.mention} has been appointed as **Deputy Minister of {ministry['name']}**."
                    ),
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    embed=create_error_embed("Error", "Failed to appoint deputy minister."),
                    ephemeral=True
                )
        except Exception as e:
            await interaction.followup.send(
                embed=create_error_embed("Error", f"Failed to appoint deputy minister: {str(e)}"),
                ephemeral=True
            )

    @app_commands.command(name="remove_ministry", description="[Chancellor] Remove a ministry")
    @app_commands.describe(ministry_name="Name of the ministry to remove")
    @app_commands.guild_only()
    async def remove_ministry(self, interaction: discord.Interaction, ministry_name: str):
        """Remove a ministry"""
        if not await is_admin_or_chancellor(interaction.user, self.bot.db):
            return await interaction.response.send_message(
                embed=create_error_embed("Permission Denied", "Only the Chancellor can remove ministries."),
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        try:
            # Find the ministry
            ministries = await get_all_ministries(self.bot.db, interaction.guild.id)
            ministry = next((m for m in ministries if m['name'].lower() == ministry_name.lower()), None)

            if not ministry:
                return await interaction.followup.send(
                    embed=create_error_embed("Not Found", f"Ministry '{ministry_name}' not found."),
                    ephemeral=True
                )

            # Remove roles from minister and deputy
            if ministry.get('minister_id'):
                member = interaction.guild.get_member(int(ministry['minister_id']))
                if member and ministry.get('role_id'):
                    role = interaction.guild.get_role(int(ministry['role_id']))
                    if role and role in member.roles:
                        await member.remove_roles(role, reason="Ministry disbanded")

            if ministry.get('deputy_minister_id'):
                member = interaction.guild.get_member(int(ministry['deputy_minister_id']))
                if member and ministry.get('deputy_role_id'):
                    role = interaction.guild.get_role(int(ministry['deputy_role_id']))
                    if role and role in member.roles:
                        await member.remove_roles(role, reason="Ministry disbanded")

            # Delete the ministry
            deleted = await delete_ministry(self.bot.db, ministry['$id'])

            if deleted:
                await interaction.followup.send(
                    embed=create_success_embed(
                        "Ministry Removed",
                        f"**{ministry['name']}** has been disbanded."
                    ),
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    embed=create_error_embed("Error", "Failed to remove ministry."),
                    ephemeral=True
                )
        except Exception as e:
            await interaction.followup.send(
                embed=create_error_embed("Error", f"Failed to remove ministry: {str(e)}"),
                ephemeral=True
            )

    @app_commands.command(name="set_ministry_role", description="[Chancellor] Set or change the role for a ministry")
    @app_commands.describe(
        ministry_name="Name of the ministry",
        role="New role for the ministry (optional to clear)",
        is_deputy="Set the deputy role instead of minister role"
    )
    @app_commands.guild_only()
    async def set_ministry_role(
        self,
        interaction: discord.Interaction,
        ministry_name: str,
        role: discord.Role = None,
        is_deputy: bool = False
    ):
        """Set ministry role"""
        if not await is_admin_or_chancellor(interaction.user, self.bot.db):
            return await interaction.response.send_message(
                embed=create_error_embed("Permission Denied", "Only the Chancellor can modify ministry roles."),
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        try:
            # Find the ministry
            ministries = await get_all_ministries(self.bot.db, interaction.guild.id)
            ministry = next((m for m in ministries if m['name'].lower() == ministry_name.lower()), None)

            if not ministry:
                return await interaction.followup.send(
                    embed=create_error_embed("Not Found", f"Ministry '{ministry_name}' not found."),
                    ephemeral=True
                )

            # Update the appropriate role
            field = "deputy_role_id" if is_deputy else "role_id"
            updated = await update_ministry(self.bot.db, ministry['$id'], {field: str(role.id) if role else ""})

            if updated:
                role_type = "Deputy" if is_deputy else "Minister"
                await interaction.followup.send(
                    embed=create_success_embed(
                        "Role Updated",
                        f"{role_type} role for **{ministry['name']}** has been " +
                        (f"set to {role.mention}" if role else "cleared")
                    ),
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    embed=create_error_embed("Error", "Failed to update role."),
                    ephemeral=True
                )
        except Exception as e:
            await interaction.followup.send(
                embed=create_error_embed("Error", f"Failed to update role: {str(e)}"),
                ephemeral=True
            )

    @app_commands.command(name="kick", description="[Chancellor] Kick a member from the server")
    @app_commands.describe(member="Member to kick", reason="Reason for kick")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        """Kick a member"""
        if not await is_admin_or_chancellor(interaction.user, self.bot.db):
            await interaction.response.send_message(
                embed=create_error_embed("Permission Denied", "Only the Chancellor can use this command."),
                ephemeral=True
            )
            return

        if member.top_role >= interaction.user.top_role:
            await interaction.response.send_message(
                embed=create_error_embed("Cannot Kick", "You cannot kick someone with equal or higher role."),
                ephemeral=True
            )
            return

        if member.bot:
            await interaction.response.send_message(
                embed=create_error_embed("Cannot Kick", "You cannot kick bots."),
                ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            await member.kick(reason=f"[Chancellor: {interaction.user}] {reason}")
            await interaction.followup.send(
                embed=create_success_embed("Member Kicked", f"{member.mention} has been kicked.\n**Reason:** {reason}")
            )
        except discord.Forbidden:
            await interaction.followup.send(
                embed=create_error_embed("Error", "I don't have permission to kick this member."),
                ephemeral=True
            )

    @app_commands.command(name="ban", description="[Chancellor] Ban a member from the server")
    @app_commands.describe(member="Member to ban", reason="Reason for ban", delete_days="Days of messages to delete (0-7)")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided", delete_days: app_commands.Range[int, 0, 7] = 0):
        """Ban a member"""
        if not await is_admin_or_chancellor(interaction.user, self.bot.db):
            await interaction.response.send_message(
                embed=create_error_embed("Permission Denied", "Only the Chancellor can use this command."),
                ephemeral=True
            )
            return

        if member.top_role >= interaction.user.top_role:
            await interaction.response.send_message(
                embed=create_error_embed("Cannot Ban", "You cannot ban someone with equal or higher role."),
                ephemeral=True
            )
            return

        if member.bot:
            await interaction.response.send_message(
                embed=create_error_embed("Cannot Ban", "You cannot ban bots."),
                ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            await member.ban(reason=f"[Chancellor: {interaction.user}] {reason}", delete_message_days=delete_days)
            await interaction.followup.send(
                embed=create_success_embed("Member Banned", f"{member.mention} has been banned.\n**Reason:** {reason}")
            )
        except discord.Forbidden:
            await interaction.followup.send(
                embed=create_error_embed("Error", "I don't have permission to ban this member."),
                ephemeral=True
            )

    @app_commands.command(name="unban", description="[Chancellor] Unban a user")
    @app_commands.describe(user_id="User ID to unban")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def unban(self, interaction: discord.Interaction, user_id: str):
        """Unban a user"""
        if not await is_admin_or_chancellor(interaction.user, self.bot.db):
            await interaction.response.send_message(
                embed=create_error_embed("Permission Denied", "Only the Chancellor can use this command."),
                ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user, reason=f"Unbanned by Chancellor: {interaction.user}")
            await interaction.followup.send(
                embed=create_success_embed("User Unbanned", f"{user.mention} has been unbanned.")
            )
        except ValueError:
            await interaction.followup.send(
                embed=create_error_embed("Invalid ID", "Please provide a valid user ID."),
                ephemeral=True
            )
        except discord.NotFound:
            await interaction.followup.send(
                embed=create_error_embed("Not Found", "This user is not banned."),
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send(
                embed=create_error_embed("Error", "I don't have permission to unban users."),
                ephemeral=True
            )

    @app_commands.command(name="timeout", description="[Chancellor] Timeout a member")
    @app_commands.describe(member="Member to timeout", duration="Duration in minutes", reason="Reason for timeout")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, duration: app_commands.Range[int, 1, 40320], reason: str = "No reason provided"):
        """Timeout a member"""
        if not await is_admin_or_chancellor(interaction.user, self.bot.db):
            await interaction.response.send_message(
                embed=create_error_embed("Permission Denied", "Only the Chancellor can use this command."),
                ephemeral=True
            )
            return

        if member.top_role >= interaction.user.top_role:
            await interaction.response.send_message(
                embed=create_error_embed("Cannot Timeout", "You cannot timeout someone with equal or higher role."),
                ephemeral=True
            )
            return

        if member.bot:
            await interaction.response.send_message(
                embed=create_error_embed("Cannot Timeout", "You cannot timeout bots."),
                ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            from datetime import timedelta
            await member.timeout(timedelta(minutes=duration), reason=f"[Chancellor: {interaction.user}] {reason}")
            await interaction.followup.send(
                embed=create_success_embed("Member Timed Out", f"{member.mention} has been timed out for {duration} minutes.\n**Reason:** {reason}")
            )
        except discord.Forbidden:
            await interaction.followup.send(
                embed=create_error_embed("Error", "I don't have permission to timeout this member."),
                ephemeral=True
            )

    @app_commands.command(name="add_role", description="[Chancellor] Add a role to a member")
    @app_commands.describe(member="Member to add role to", role="Role to add")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def add_role(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        """Add a role to a member"""
        if not await is_admin_or_chancellor(interaction.user, self.bot.db):
            await interaction.response.send_message(
                embed=create_error_embed("Permission Denied", "Only the Chancellor can use this command."),
                ephemeral=True
            )
            return

        if role >= interaction.user.top_role:
            await interaction.response.send_message(
                embed=create_error_embed("Cannot Assign", "You cannot assign a role equal to or higher than your own."),
                ephemeral=True
            )
            return

        if role in member.roles:
            await interaction.response.send_message(
                embed=create_error_embed("Already Has Role", f"{member.mention} already has {role.mention}."),
                ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            await member.add_roles(role, reason=f"Added by Chancellor: {interaction.user}")
            await interaction.followup.send(
                embed=create_success_embed("Role Added", f"Added {role.mention} to {member.mention}.")
            )
        except discord.Forbidden:
            await interaction.followup.send(
                embed=create_error_embed("Error", "I don't have permission to manage this role."),
                ephemeral=True
            )

    @app_commands.command(name="remove_role", description="[Chancellor] Remove a role from a member")
    @app_commands.describe(member="Member to remove role from", role="Role to remove")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def remove_role(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        """Remove a role from a member"""
        if not await is_admin_or_chancellor(interaction.user, self.bot.db):
            await interaction.response.send_message(
                embed=create_error_embed("Permission Denied", "Only the Chancellor can use this command."),
                ephemeral=True
            )
            return

        if role >= interaction.user.top_role:
            await interaction.response.send_message(
                embed=create_error_embed("Cannot Remove", "You cannot remove a role equal to or higher than your own."),
                ephemeral=True
            )
            return

        if role not in member.roles:
            await interaction.response.send_message(
                embed=create_error_embed("Doesn't Have Role", f"{member.mention} doesn't have {role.mention}."),
                ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            await member.remove_roles(role, reason=f"Removed by Chancellor: {interaction.user}")
            await interaction.followup.send(
                embed=create_success_embed("Role Removed", f"Removed {role.mention} from {member.mention}.")
            )
        except discord.Forbidden:
            await interaction.followup.send(
                embed=create_error_embed("Error", "I don't have permission to manage this role."),
                ephemeral=True
            )

    @app_commands.command(name="lock_channel", description="[Chancellor] Lock a channel")
    @app_commands.describe(channel="Channel to lock")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def lock_channel(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        """Lock a channel (prevent @everyone from sending messages)"""
        if not await is_admin_or_chancellor(interaction.user, self.bot.db):
            await interaction.response.send_message(
                embed=create_error_embed("Permission Denied", "Only the Chancellor can use this command."),
                ephemeral=True
            )
            return

        channel = channel or interaction.channel

        await interaction.response.defer()

        try:
            await channel.set_permissions(
                interaction.guild.default_role,
                send_messages=False,
                reason=f"Locked by Chancellor: {interaction.user}"
            )
            await interaction.followup.send(
                embed=create_success_embed("Channel Locked", f"{channel.mention} has been locked.")
            )
        except discord.Forbidden:
            await interaction.followup.send(
                embed=create_error_embed("Error", "I don't have permission to manage this channel."),
                ephemeral=True
            )

    @app_commands.command(name="unlock_channel", description="[Chancellor] Unlock a channel")
    @app_commands.describe(channel="Channel to unlock")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def unlock_channel(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        """Unlock a channel"""
        if not await is_admin_or_chancellor(interaction.user, self.bot.db):
            await interaction.response.send_message(
                embed=create_error_embed("Permission Denied", "Only the Chancellor can use this command."),
                ephemeral=True
            )
            return

        channel = channel or interaction.channel

        await interaction.response.defer()

        try:
            await channel.set_permissions(
                interaction.guild.default_role,
                send_messages=None,
                reason=f"Unlocked by Chancellor: {interaction.user}"
            )
            await interaction.followup.send(
                embed=create_success_embed("Channel Unlocked", f"{channel.mention} has been unlocked.")
            )
        except discord.Forbidden:
            await interaction.followup.send(
                embed=create_error_embed("Error", "I don't have permission to manage this channel."),
                ephemeral=True
            )

    @app_commands.command(name="purge", description="[Chancellor] Delete multiple messages")
    @app_commands.describe(amount="Number of messages to delete (1-100)")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def purge(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100]):
        """Bulk delete messages"""
        if not await is_admin_or_chancellor(interaction.user, self.bot.db):
            await interaction.response.send_message(
                embed=create_error_embed("Permission Denied", "Only the Chancellor can use this command."),
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            deleted = await interaction.channel.purge(limit=amount, reason=f"Purged by Chancellor: {interaction.user}")
            await interaction.followup.send(
                embed=create_success_embed("Messages Purged", f"Deleted {len(deleted)} messages."),
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send(
                embed=create_error_embed("Error", "I don't have permission to delete messages."),
                ephemeral=True
            )

    @app_commands.command(name="announce", description="[Chancellor] Send an official announcement")
    @app_commands.describe(channel="Channel to send announcement", title="Announcement title", message="Announcement message")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def announce(self, interaction: discord.Interaction, channel: discord.TextChannel, title: str, message: str):
        """Send an official government announcement"""
        if not await is_admin_or_chancellor(interaction.user, self.bot.db):
            await interaction.response.send_message(
                embed=create_error_embed("Permission Denied", "Only the Chancellor can use this command."),
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"📢 {title}",
            description=message,
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Issued by Chancellor {interaction.user.display_name}")
        embed.timestamp = discord.utils.utcnow()

        await interaction.response.defer(ephemeral=True)

        try:
            await channel.send(embed=embed)
            await interaction.followup.send(
                embed=create_success_embed("Announcement Sent", f"Announcement sent to {channel.mention}."),
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send(
                embed=create_error_embed("Error", "I don't have permission to send messages in that channel."),
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Executive(bot))
