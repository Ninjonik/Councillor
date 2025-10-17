import discord
from discord import app_commands
from discord.ext import commands
from appwrite.id import ID
from appwrite.query import Query
import config
import utils
import embeds

BOT_ADMIN_ID = 231105080961531905

def is_bot_admin():
    def predicate(interaction: discord.Interaction) -> bool:
        return interaction.user.id == BOT_ADMIN_ID
    return app_commands.check(predicate)

class Admin(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client

    @app_commands.command(name="setup_guild", description="[Admin] Initialize guild configuration")
    @is_bot_admin()
    async def setup_guild(
        self,
        interaction: discord.Interaction,
        councillor_role: discord.Role,
        chancellor_role: discord.Role = None,
        president_role: discord.Role = None,
        vice_president_role: discord.Role = None,
        judiciary_role: discord.Role = None,
        voting_channel: discord.TextChannel = None
    ):
        try:
            guild_id = str(interaction.guild.id)

            data = {'councillor_role_id': str(councillor_role.id)}

            if chancellor_role:
                data['chancellor_role_id'] = str(chancellor_role.id)
            if president_role:
                data['president_role_id'] = str(president_role.id)
            if vice_president_role:
                data['vice_president_role_id'] = str(vice_president_role.id)
            if judiciary_role:
                data['judiciary_role_id'] = str(judiciary_role.id)
            if voting_channel:
                data['voting_channel_id'] = str(voting_channel.id)

            try:
                self.client.db.create_document(
                    database_id=config.APPWRITE_DB_NAME,
                    collection_id='guilds',
                    document_id=guild_id,
                    data=data
                )
                msg = "Guild configuration created!"
            except:
                self.client.db.update_document(
                    database_id=config.APPWRITE_DB_NAME,
                    collection_id='guilds',
                    document_id=guild_id,
                    data=data
                )
                msg = "Guild configuration updated!"

            await interaction.response.send_message(
                embed=embeds.create_success_embed("Configuration Saved", msg),
                ephemeral=True
            )
        except Exception as e:
            await utils.handle_interaction_error(interaction, e)

    @app_commands.command(name="appoint_councillor", description="[Admin] Manually appoint someone as councillor")
    @is_bot_admin()
    async def appoint_councillor(self, interaction: discord.Interaction, member: discord.Member):
        try:
            guild_data = utils.get_guild_data(self.client.db, interaction.guild.id)
            if not guild_data or not guild_data.get("councillor_role_id"):
                return await interaction.response.send_message(
                    embed=embeds.create_error_embed("Config Error", "Councillor role not configured!"),
                    ephemeral=True
                )

            council_id = str(interaction.guild.id) + "_c"

            existing = await utils.get_councillor_data(self.client.db, member.id, interaction.guild.id)
            if existing:
                return await interaction.response.send_message(
                    embed=embeds.create_error_embed("Already Councillor", f"{member.mention} is already a councillor!"),
                    ephemeral=True
                )

            self.client.db.create_document(
                database_id=config.APPWRITE_DB_NAME,
                collection_id='councillors',
                document_id=ID.unique(),
                data={
                    'discord_id': str(member.id),
                    'name': member.display_name,
                    'council': council_id
                }
            )

            councillor_role = interaction.guild.get_role(int(guild_data['councillor_role_id']))
            if councillor_role:
                await member.add_roles(councillor_role, reason=f"Appointed by {interaction.user.name}")

            await interaction.response.send_message(
                embed=embeds.create_success_embed("Councillor Appointed", f"{member.mention} is now a councillor!"),
                ephemeral=True
            )
        except Exception as e:
            await utils.handle_interaction_error(interaction, e)

    @app_commands.command(name="remove_councillor", description="[Admin] Remove someone from councillor position")
    @is_bot_admin()
    async def remove_councillor(self, interaction: discord.Interaction, member: discord.Member):
        try:
            councillor_data = await utils.get_councillor_data(self.client.db, member.id, interaction.guild.id)
            if not councillor_data:
                return await interaction.response.send_message(
                    embed=embeds.create_error_embed("Not Found", f"{member.mention} is not a councillor!"),
                    ephemeral=True
                )

            self.client.db.delete_document(
                database_id=config.APPWRITE_DB_NAME,
                collection_id='councillors',
                document_id=councillor_data["$id"]
            )

            guild_data = utils.get_guild_data(self.client.db, interaction.guild.id)
            if guild_data and guild_data.get('councillor_role_id'):
                councillor_role = interaction.guild.get_role(int(guild_data['councillor_role_id']))
                if councillor_role:
                    await member.remove_roles(councillor_role, reason=f"Removed by {interaction.user.name}")

            await interaction.response.send_message(
                embed=embeds.create_success_embed("Councillor Removed", f"{member.mention} removed from Council!"),
                ephemeral=True
            )
        except Exception as e:
            await utils.handle_interaction_error(interaction, e)

    @app_commands.command(name="set_role", description="[Admin] Configure a specific role for the guild")
    @is_bot_admin()
    @app_commands.choices(role_type=[
        app_commands.Choice(name="Councillor", value="councillor_role_id"),
        app_commands.Choice(name="Chancellor", value="chancellor_role_id"),
        app_commands.Choice(name="President", value="president_role_id"),
        app_commands.Choice(name="Vice President", value="vice_president_role_id"),
        app_commands.Choice(name="Chief Justice", value="judiciary_role_id"),
    ])
    async def set_role(self, interaction: discord.Interaction, role_type: app_commands.Choice[str], role: discord.Role):
        try:
            guild_id = str(interaction.guild.id)

            try:
                self.client.db.update_document(
                    database_id=config.APPWRITE_DB_NAME,
                    collection_id='guilds',
                    document_id=guild_id,
                    data={role_type.value: str(role.id)}
                )
            except:
                self.client.db.create_document(
                    database_id=config.APPWRITE_DB_NAME,
                    collection_id='guilds',
                    document_id=guild_id,
                    data={role_type.value: str(role.id)}
                )

            await interaction.response.send_message(
                embed=embeds.create_success_embed("Role Configured", f"{role_type.name} → {role.mention}"),
                ephemeral=True
            )
        except Exception as e:
            await utils.handle_interaction_error(interaction, e)

    @app_commands.command(name="set_voting_channel", description="[Admin] Set the voting channel")
    @is_bot_admin()
    async def set_voting_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        try:
            guild_id = str(interaction.guild.id)

            try:
                self.client.db.update_document(
                    database_id=config.APPWRITE_DB_NAME,
                    collection_id='guilds',
                    document_id=guild_id,
                    data={'voting_channel_id': str(channel.id)}
                )
            except:
                self.client.db.create_document(
                    database_id=config.APPWRITE_DB_NAME,
                    collection_id='guilds',
                    document_id=guild_id,
                    data={'voting_channel_id': str(channel.id)}
                )

            await interaction.response.send_message(
                embed=embeds.create_success_embed("Channel Set", f"Voting channel: {channel.mention}"),
                ephemeral=True
            )
        except Exception as e:
            await utils.handle_interaction_error(interaction, e)

    @app_commands.command(name="cancel_voting", description="[Admin] Cancel an ongoing vote")
    @is_bot_admin()
    async def cancel_voting(self, interaction: discord.Interaction, voting_message_id: str):
        try:
            voting = self.client.db.get_document(
                database_id=config.APPWRITE_DB_NAME,
                collection_id='votings',
                document_id=voting_message_id
            )

            self.client.db.update_document(
                database_id=config.APPWRITE_DB_NAME,
                collection_id='votings',
                document_id=voting_message_id,
                data={'status': 'cancelled'}
            )

            await interaction.response.send_message(
                embed=embeds.create_success_embed("Vote Cancelled", f"'{voting['title']}' has been cancelled."),
                ephemeral=True
            )
        except Exception as e:
            await utils.handle_interaction_error(interaction, e, "Voting not found")

    @app_commands.command(name="view_config", description="[Admin] View current guild configuration")
    @is_bot_admin()
    async def view_config(self, interaction: discord.Interaction):
        try:
            guild_data = utils.get_guild_data(self.client.db, interaction.guild.id)

            if not guild_data:
                return await interaction.response.send_message(
                    embed=embeds.create_error_embed("Not Configured", "Guild not configured yet!"),
                    ephemeral=True
                )

            embed = embeds.create_info_embed("Guild Configuration", "Current server settings:", 0x3498DB)

            role_fields = [
                ('councillor_role_id', 'Councillor Role'),
                ('chancellor_role_id', 'Chancellor Role'),
                ('president_role_id', 'President Role'),
                ('vice_president_role_id', 'Vice President Role'),
                ('judiciary_role_id', 'Chief Justice Role')
            ]

            for field_id, field_name in role_fields:
                if guild_data.get(field_id):
                    role = interaction.guild.get_role(int(guild_data[field_id]))
                    embed.add_field(name=field_name, value=role.mention if role else "❌ Not found", inline=True)

            if guild_data.get('voting_channel_id'):
                channel = interaction.guild.get_channel(int(guild_data['voting_channel_id']))
                embed.add_field(name="Voting Channel", value=channel.mention if channel else "❌ Not found", inline=False)

            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await utils.handle_interaction_error(interaction, e)

    @app_commands.command(name="list_councillors", description="[Admin] List all councillors")
    @is_bot_admin()
    async def list_councillors(self, interaction: discord.Interaction):
        try:
            council_id = str(interaction.guild.id) + "_c"
            result = self.client.db.list_documents(
                database_id=config.APPWRITE_DB_NAME,
                collection_id='councillors',
                queries=[Query.equal('council', council_id)]
            )

            councillors = result["documents"]

            if not councillors:
                return await interaction.response.send_message(
                    embed=embeds.create_info_embed("No Councillors", "No councillors found in this server."),
                    ephemeral=True
                )

            embed = embeds.create_info_embed(
                "Councillors List",
                f"Total: {len(councillors)} councillor{'s' if len(councillors) != 1 else ''}",
                0x2ECC71
            )

            for councillor in councillors[:25]:
                member = interaction.guild.get_member(int(councillor['discord_id']))
                status = "✅ Active" if member else "❌ Left server"
                embed.add_field(
                    name=councillor['name'],
                    value=f"{status}\nID: `{councillor['discord_id']}`",
                    inline=True
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await utils.handle_interaction_error(interaction, e)

    @app_commands.command(name="cleanup_councillors", description="[Admin] Remove councillors who left")
    @is_bot_admin()
    async def cleanup_councillors(self, interaction: discord.Interaction):
        try:
            council_id = str(interaction.guild.id) + "_c"
            result = self.client.db.list_documents(
                database_id=config.APPWRITE_DB_NAME,
                collection_id='councillors',
                queries=[Query.equal('council', council_id)]
            )

            removed = 0
            for councillor in result["documents"]:
                member = interaction.guild.get_member(int(councillor['discord_id']))
                if not member:
                    self.client.db.delete_document(
                        database_id=config.APPWRITE_DB_NAME,
                        collection_id='councillors',
                        document_id=councillor['$id']
                    )
                    removed += 1

            await interaction.response.send_message(
                embed=embeds.create_success_embed("Cleanup Complete", f"Removed {removed} councillor(s) who left the server."),
                ephemeral=True
            )
        except Exception as e:
            await utils.handle_interaction_error(interaction, e)

async def setup(client: commands.Bot) -> None:
    await client.add_cog(Admin(client))
