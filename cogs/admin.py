import discord
from discord import app_commands
from discord.ext import commands
from embeds import create_success_embed, create_error_embed
from utils import create_guild_data, get_guild_data
import config
from appwrite.id import ID

# Admin user ID - has wildcard permissions
ADMIN_USER_ID = 231105080961531905

class Admin(commands.Cog):
    """Bot admin commands"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup", description="[Admin] Initial bot setup - configure government roles")
    @app_commands.describe(
        president_role="Role for President",
        vice_president_role="Role for Vice President",
        chancellor_role="Role for Chancellor",
        councillor_role="Role for Councillors",
        citizen_role="Role for Citizens (optional)"
    )
    @app_commands.guild_only()
    async def setup(
        self,
        interaction: discord.Interaction,
        president_role: discord.Role,
        vice_president_role: discord.Role,
        chancellor_role: discord.Role,
        councillor_role: discord.Role,
        citizen_role: discord.Role = None
    ):
        """Setup the bot with government roles"""
        # Check if user is admin or has administrator permission
        if interaction.user.id != ADMIN_USER_ID and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                embed=create_error_embed("Permission Denied", "Only administrators can run setup."),
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        try:
            # Check if guild already exists in database
            guild_data = get_guild_data(self.bot.db, interaction.guild.id)

            # Prepare data
            data = {
                "guild_id": str(interaction.guild.id),
                "president_role_id": str(president_role.id),
                "vice_president_role_id": str(vice_president_role.id),
                "chancellor_role_id": str(chancellor_role.id),
                "councillor_role_id": str(councillor_role.id)
            }

            if citizen_role:
                data["citizen_role_id"] = str(citizen_role.id)

            # Create or update guild data
            if guild_data:
                # Update existing
                self.bot.db.update_document(
                    database_id=config.APPWRITE_DATABASE_ID,
                    collection_id=config.COLLECTION_GUILDS,
                    document_id=guild_data["$id"],
                    data=data
                )
            else:
                # Create new
                self.bot.db.create_document(
                    database_id=config.APPWRITE_DATABASE_ID,
                    collection_id=config.COLLECTION_GUILDS,
                    document_id=ID.unique(),
                    data=data
                )

            embed = create_success_embed(
                "✅ Setup Complete!",
                f"Government roles have been configured:\n\n"
                f"👑 **President:** {president_role.mention}\n"
                f"🎩 **Vice President:** {vice_president_role.mention}\n"
                f"⚖️ **Chancellor:** {chancellor_role.mention}\n"
                f"🎖️ **Councillor:** {councillor_role.mention}\n" +
                (f"👥 **Citizen:** {citizen_role.mention}\n" if citizen_role else "") +
                f"\nThe bot is now ready to use!"
            )
            embed.set_footer(text="You can now start using election and governance commands")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(
                embed=create_error_embed("Setup Failed", f"Error: {str(e)}"),
                ephemeral=True
            )

    @app_commands.command(name="update_roles", description="[Admin] Update configured roles")
    @app_commands.describe(
        president_role="Role for President (optional)",
        vice_president_role="Role for Vice President (optional)",
        chancellor_role="Role for Chancellor (optional)",
        councillor_role="Role for Councillors (optional)",
        citizen_role="Role for Citizens (optional)"
    )
    @app_commands.guild_only()
    async def update_roles(
        self,
        interaction: discord.Interaction,
        president_role: discord.Role = None,
        vice_president_role: discord.Role = None,
        chancellor_role: discord.Role = None,
        councillor_role: discord.Role = None,
        citizen_role: discord.Role = None
    ):
        """Update specific roles without running full setup"""
        if interaction.user.id != ADMIN_USER_ID and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                embed=create_error_embed("Permission Denied", "Only administrators can update roles."),
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        try:
            guild_data = get_guild_data(self.bot.db, interaction.guild.id)

            if not guild_data:
                return await interaction.followup.send(
                    embed=create_error_embed("Setup Required", "Please run `/setup` first to configure the bot."),
                    ephemeral=True
                )

            # Build update data
            data = {}
            changes = []

            if president_role:
                data["president_role_id"] = str(president_role.id)
                changes.append(f"👑 **President:** {president_role.mention}")
            if vice_president_role:
                data["vice_president_role_id"] = str(vice_president_role.id)
                changes.append(f"🎩 **Vice President:** {vice_president_role.mention}")
            if chancellor_role:
                data["chancellor_role_id"] = str(chancellor_role.id)
                changes.append(f"⚖️ **Chancellor:** {chancellor_role.mention}")
            if councillor_role:
                data["councillor_role_id"] = str(councillor_role.id)
                changes.append(f"🎖️ **Councillor:** {councillor_role.mention}")
            if citizen_role:
                data["citizen_role_id"] = str(citizen_role.id)
                changes.append(f"👥 **Citizen:** {citizen_role.mention}")

            if not data:
                return await interaction.followup.send(
                    embed=create_error_embed("No Changes", "Please specify at least one role to update."),
                    ephemeral=True
                )

            # Update
            self.bot.db.update_document(
                database_id=config.APPWRITE_DATABASE_ID,
                collection_id=config.COLLECTION_GUILDS,
                document_id=guild_data["$id"],
                data=data
            )

            embed = create_success_embed(
                "✅ Roles Updated!",
                "The following roles have been updated:\n\n" + "\n".join(changes)
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(
                embed=create_error_embed("Update Failed", f"Error: {str(e)}"),
                ephemeral=True
            )

    @app_commands.command(name="view_config", description="[Admin] View current bot configuration")
    @app_commands.guild_only()
    async def view_config(self, interaction: discord.Interaction):
        """View current bot configuration"""
        if interaction.user.id != ADMIN_USER_ID and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                embed=create_error_embed("Permission Denied", "Only administrators can view configuration."),
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        try:
            guild_data = get_guild_data(self.bot.db, interaction.guild.id)

            if not guild_data:
                return await interaction.followup.send(
                    embed=create_error_embed("Setup Required", "Bot has not been configured yet. Run `/setup` first."),
                    ephemeral=True
                )

            embed = discord.Embed(
                title="⚙️ Bot Configuration",
                description=f"Current configuration for **{interaction.guild.name}**",
                color=discord.Color.blue()
            )

            # Show configured roles
            roles_text = []
            for role_type in ["president", "vice_president", "chancellor", "councillor", "citizen"]:
                role_id = guild_data.get(f"{role_type}_role_id")
                if role_id:
                    role = interaction.guild.get_role(int(role_id))
                    if role:
                        roles_text.append(f"**{role_type.replace('_', ' ').title()}:** {role.mention}")
                    else:
                        roles_text.append(f"**{role_type.replace('_', ' ').title()}:** Role not found (ID: {role_id})")
                else:
                    roles_text.append(f"**{role_type.replace('_', ' ').title()}:** Not configured")

            embed.add_field(name="📋 Configured Roles", value="\n".join(roles_text), inline=False)
            embed.set_footer(text="Use /update_roles to modify configuration")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(
                embed=create_error_embed("Error", f"Failed to fetch configuration: {str(e)}"),
                ephemeral=True
            )

    @app_commands.command(name="sync_commands", description="[Admin] Sync slash commands")
    @app_commands.guild_only()
    async def sync_commands(self, interaction: discord.Interaction):
        """Sync slash commands to the guild"""
        if interaction.user.id != ADMIN_USER_ID and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                embed=create_error_embed("Permission Denied", "Only administrators can sync commands."),
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        try:
            synced = await self.bot.tree.sync(guild=interaction.guild)
            await interaction.followup.send(
                embed=create_success_embed("Commands Synced", f"Synced {len(synced)} commands to this server."),
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                embed=create_error_embed("Sync Failed", f"Error: {str(e)}"),
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Admin(bot))
