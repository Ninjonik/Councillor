import discord
from discord import app_commands
from discord.ext import commands
from utils import is_councillor, is_chancellor, is_president, is_vice_president, is_citizen, get_councillor_data, get_guild_data, get_role_by_type
from embeds import create_success_embed, create_error_embed, create_info_embed
import config

class Governance(commands.Cog):
    """Governance and information commands"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="register", description="Register as a citizen")
    @app_commands.guild_only()
    async def register(self, interaction: discord.Interaction):
        """Register a new citizen"""
        await interaction.response.defer(ephemeral=True)

        try:
            # Get guild config
            guild_data = get_guild_data(self.bot.db, interaction.guild.id)

            if not guild_data:
                await interaction.followup.send(
                    embed=create_error_embed("Setup Required", "This server hasn't been configured yet. Contact an admin."),
                    ephemeral=True
                )
                return

            # Check if already has citizen role
            if is_citizen(interaction.user, guild_data):
                await interaction.followup.send(
                    embed=create_info_embed("Already Registered", "You are already registered as a Citizen."),
                    ephemeral=True
                )
                return

            # Add citizen role
            citizen_role = get_role_by_type(interaction.guild, guild_data, "citizen")
            if citizen_role:
                try:
                    await interaction.user.add_roles(citizen_role)
                    await interaction.followup.send(
                        embed=create_success_embed("Registration Complete", "You are now registered as a Citizen! You can now vote in elections and run for office."),
                        ephemeral=True
                    )
                except discord.Forbidden:
                    await interaction.followup.send(
                        embed=create_error_embed("Role Error", "Couldn't assign role. Contact an admin."),
                        ephemeral=True
                    )
            else:
                await interaction.followup.send(
                    embed=create_error_embed("Error", "Citizen role not configured. Contact an admin."),
                    ephemeral=True
                )
        except Exception as e:
            await interaction.followup.send(
                embed=create_error_embed("Error", f"An unexpected error occurred: {str(e)}"),
                ephemeral=True
            )

    @app_commands.command(name="government", description="View current government members")
    @app_commands.guild_only()
    async def government(self, interaction: discord.Interaction):
        """Display current government members"""
        await interaction.response.defer()

        try:
            # Get guild config
            guild_data = get_guild_data(self.bot.db, interaction.guild.id)

            if not guild_data:
                await interaction.followup.send(
                    embed=create_error_embed("Setup Required", "This server hasn't been configured yet."),
                    ephemeral=True
                )
                return

            embed = create_info_embed("🏛️ Current Government", "")

            # Find President
            president_role = get_role_by_type(interaction.guild, guild_data, "president")
            if president_role and president_role.members:
                embed.add_field(name="🇺🇸 President", value=president_role.members[0].mention, inline=True)
            else:
                embed.add_field(name="🇺🇸 President", value="*Vacant*", inline=True)

            # Find Vice President
            vp_role = get_role_by_type(interaction.guild, guild_data, "vice_president")
            if vp_role and vp_role.members:
                embed.add_field(name="🎩 Vice President", value=vp_role.members[0].mention, inline=True)
            else:
                embed.add_field(name="🎩 Vice President", value="*Vacant*", inline=True)

            # Find Chancellor
            chancellor_role = get_role_by_type(interaction.guild, guild_data, "chancellor")
            if chancellor_role and chancellor_role.members:
                chancellor_list = "\n".join([m.mention for m in chancellor_role.members])
                embed.add_field(name="👑 Chancellor", value=chancellor_list, inline=False)
            else:
                embed.add_field(name="👑 Chancellor", value="*Vacant*", inline=False)

            # Find Councillors
            councillor_role = get_role_by_type(interaction.guild, guild_data, "councillor")
            if councillor_role and councillor_role.members:
                councillor_list = "\n".join([m.mention for m in councillor_role.members])
                embed.add_field(name="🎖️ Councillors", value=councillor_list, inline=False)
            else:
                embed.add_field(name="🎖️ Councillors", value="*None*", inline=False)

            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(
                embed=create_error_embed("Error", f"Failed to fetch government: {str(e)}"),
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Governance(bot))
