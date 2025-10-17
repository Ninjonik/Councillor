import discord
from discord import app_commands
from discord.ext import commands
from appwrite.id import ID
from datetime import datetime, timedelta
import config
import utils
import embeds

class Executive(commands.Cog):
    """Chancellor and President executive commands"""

    def __init__(self, client: commands.Bot):
        self.client = client

    async def is_president_or_vp(self, interaction: discord.Interaction) -> bool:
        is_pres = await utils.is_eligible(self.client.db, interaction.user, interaction.guild, "president")
        is_vp = await utils.is_eligible(self.client.db, interaction.user, interaction.guild, "vice_president")
        return is_pres or is_vp

    @app_commands.command(name="appoint", description="[Chancellor] Appoint a minister or official")
    async def appoint_minister(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        position: str,
        deputy: bool = False
    ):
        try:
            if not await utils.is_eligible(self.client.db, interaction.user, interaction.guild, "chancellor"):
                return await interaction.response.send_message(
                    embed=embeds.create_error_embed("Not Authorized", "Only the Chancellor can appoint ministers."),
                    ephemeral=True
                )

            title = f"{'Deputy ' if deputy else ''}{position}"

            embed = embeds.create_ministerial_appointment_embed(
                member, title, interaction.user, is_removal=False
            )

            guild_data = utils.get_guild_data(self.client.db, interaction.guild.id)
            if guild_data and guild_data.get('voting_channel_id'):
                channel = interaction.guild.get_channel(int(guild_data['voting_channel_id']))
                if channel:
                    await channel.send(embed=embed)

            await interaction.response.send_message(
                embed=embeds.create_success_embed(
                    "Appointment Confirmed",
                    f"{member.mention} has been appointed as {title}."
                ),
                ephemeral=True
            )
        except Exception as e:
            await utils.handle_interaction_error(interaction, e)

    @app_commands.command(name="dismiss", description="[Chancellor] Remove a minister from office")
    async def remove_minister(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        position: str,
        reason: str = "No reason provided"
    ):
        try:
            if not await utils.is_eligible(self.client.db, interaction.user, interaction.guild, "chancellor"):
                return await interaction.response.send_message(
                    embed=embeds.create_error_embed("Not Authorized", "Only the Chancellor can dismiss ministers."),
                    ephemeral=True
                )

            embed = embeds.create_ministerial_appointment_embed(
                member, position, interaction.user, is_removal=True
            )
            embed.add_field(name="📝 Reason", value=reason, inline=False)

            guild_data = utils.get_guild_data(self.client.db, interaction.guild.id)
            if guild_data and guild_data.get('voting_channel_id'):
                channel = interaction.guild.get_channel(int(guild_data['voting_channel_id']))
                if channel:
                    await channel.send(embed=embed)

            await interaction.response.send_message(
                embed=embeds.create_success_embed(
                    "Dismissal Confirmed",
                    f"{member.mention} has been removed from the position of {position}."
                ),
                ephemeral=True
            )
        except Exception as e:
            await utils.handle_interaction_error(interaction, e)

    @app_commands.command(name="decree", description="[Chancellor] Issue an emergency decree")
    async def emergency_decree(self, interaction: discord.Interaction, title: str, decree_text: str):
        try:
            if not await utils.is_eligible(self.client.db, interaction.user, interaction.guild, "chancellor"):
                return await interaction.response.send_message(
                    embed=embeds.create_error_embed("Not Authorized", "Only the Chancellor can issue decrees."),
                    ephemeral=True
                )

            embed = discord.Embed(
                title=f"🛑 DECREE: {title}",
                description=f"**Issued by Chancellor {interaction.user.mention}**\n\n{decree_text}",
                color=0xFFA500,
                timestamp=utils.datetime_now()
            )
            embed.add_field(
                name="⚖️ Subject to Review",
                value="This decree takes immediate effect but will be reviewed by the Grand Council. "
                      "The Council may override with a 2/3 majority vote.",
                inline=False
            )

            guild_data = utils.get_guild_data(self.client.db, interaction.guild.id)
            channel = interaction.guild.get_channel(int(guild_data["voting_channel_id"]))

            await channel.send(embed=embed)
            await interaction.response.send_message(
                embed=embeds.create_success_embed(
                    "Decree Issued",
                    "Your decree has been posted and is now in effect."
                ),
                ephemeral=True
            )
        except Exception as e:
            await utils.handle_interaction_error(interaction, e)

    @app_commands.command(name="assign_committee", description="[Chancellor] Assign oversight committee")
    async def assign_committee(
        self,
        interaction: discord.Interaction,
        councillor: discord.Member,
        committee: str
    ):
        try:
            if not await utils.is_eligible(self.client.db, interaction.user, interaction.guild, "chancellor"):
                return await interaction.response.send_message(
                    embed=embeds.create_error_embed("Not Authorized", "Only the Chancellor can assign committees."),
                    ephemeral=True
                )

            councillor_data = await utils.get_councillor_data(self.client.db, councillor.id, interaction.guild.id)
            if not councillor_data:
                return await interaction.response.send_message(
                    embed=embeds.create_error_embed("Invalid Selection", f"{councillor.mention} is not a councillor."),
                    ephemeral=True
                )

            embed = discord.Embed(
                title="🏛️ Committee Assignment",
                description=f"**{councillor.mention}** has been assigned to oversee **{committee}**",
                color=0x3498DB,
                timestamp=utils.datetime_now()
            )
            embed.add_field(name="Assigned By", value=interaction.user.mention, inline=True)
            embed.set_footer(text="Per Constitution Article 3.3")

            guild_data = utils.get_guild_data(self.client.db, interaction.guild.id)
            if guild_data and guild_data.get('voting_channel_id'):
                channel = interaction.guild.get_channel(int(guild_data['voting_channel_id']))
                if channel:
                    await channel.send(embed=embed)

            await interaction.response.send_message(
                embed=embeds.create_success_embed(
                    "Committee Assigned",
                    f"{councillor.mention} will now oversee {committee}."
                ),
                ephemeral=True
            )
        except Exception as e:
            await utils.handle_interaction_error(interaction, e)

    @app_commands.command(name="veto", description="[President/VP/Chancellor] Veto legislation")
    async def veto_law(self, interaction: discord.Interaction, voting_message_id: str, reason: str):
        try:
            is_chancellor = await utils.is_eligible(self.client.db, interaction.user, interaction.guild, "chancellor")
            is_exec = await self.is_president_or_vp(interaction)

            if not (is_chancellor or is_exec):
                return await interaction.response.send_message(
                    embed=embeds.create_error_embed(
                        "Not Authorized",
                        "Only the President, Vice President, or Chancellor can veto legislation."
                    ),
                    ephemeral=True
                )

            voting = self.client.db.get_document(
                database_id=config.APPWRITE_DB_NAME,
                collection_id="votings",
                document_id=voting_message_id
            )

            role_title = "Chancellor"
            if await utils.is_eligible(self.client.db, interaction.user, interaction.guild, "president"):
                role_title = "President"
            elif await utils.is_eligible(self.client.db, interaction.user, interaction.guild, "vice_president"):
                role_title = "Vice President"

            guild_data = utils.get_guild_data(self.client.db, interaction.guild.id)
            channel = interaction.guild.get_channel(int(guild_data["voting_channel_id"]))

            embed = embeds.create_error_embed(
                f"{voting['title']} - VETOED",
                f"This legislation has been vetoed by {role_title} {interaction.user.mention}"
            )
            embed.add_field(name="📝 Reason", value=reason, inline=False)
            embed.add_field(
                name="⚖️ Override Option",
                value="The Grand Council may override this veto with a 2/3 majority vote.",
                inline=False
            )

            if voting.get('proposer'):
                councillor = self.client.db.get_document(
                    database_id=config.APPWRITE_DB_NAME,
                    collection_id='councillors',
                    document_id=voting['proposer']
                )
                embed.set_footer(text=f"Originally proposed by {councillor['name']}")

            await channel.send(embed=embed)
            await interaction.response.send_message(
                embed=embeds.create_success_embed("Veto Confirmed", "Legislation has been vetoed."),
                ephemeral=True
            )
        except Exception as e:
            await utils.handle_interaction_error(interaction, e)

    @app_commands.command(name="declare_emergency", description="[President] Declare state of emergency")
    async def declare_emergency(
        self,
        interaction: discord.Interaction,
        reason: str,
        duration_days: int = 7
    ):
        try:
            if not await utils.is_eligible(self.client.db, interaction.user, interaction.guild, "president"):
                return await interaction.response.send_message(
                    embed=embeds.create_error_embed(
                        "Not Authorized",
                        "Only the President can declare a state of emergency."
                    ),
                    ephemeral=True
                )

            if duration_days > 30:
                return await interaction.response.send_message(
                    embed=embeds.create_error_embed(
                        "Invalid Duration",
                        "Emergency cannot exceed 30 days without Council extension."
                    ),
                    ephemeral=True
                )

            end_date = utils.datetime_now() + timedelta(days=duration_days)

            embed = embeds.create_emergency_embed(
                "STATE OF EMERGENCY DECLARED",
                f"President {interaction.user.mention} has declared a state of emergency.",
                interaction.user,
                {
                    "📋 Reason": reason,
                    "⏱️ Duration": f"{duration_days} days (expires <t:{int(end_date.timestamp())}:R>)",
                    "⚡ Emergency Powers": "• President assumes Grand Council functions\n"
                                          "• Constitution temporarily suspended (except human rights)\n"
                                          "• Emergency decrees have immediate effect\n"
                                          "• President may remove/appoint officials"
                }
            )

            guild_data = utils.get_guild_data(self.client.db, interaction.guild.id)
            channel = interaction.guild.get_channel(int(guild_data["voting_channel_id"]))

            await channel.send("@everyone", embed=embed)
            await interaction.response.send_message(
                embed=embeds.create_success_embed(
                    "Emergency Declared",
                    f"State of emergency is now active for {duration_days} days."
                ),
                ephemeral=True
            )
        except Exception as e:
            await utils.handle_interaction_error(interaction, e)

    @app_commands.command(name="end_emergency", description="[President] End state of emergency")
    async def end_emergency(self, interaction: discord.Interaction, summary: str):
        try:
            if not await utils.is_eligible(self.client.db, interaction.user, interaction.guild, "president"):
                return await interaction.response.send_message(
                    embed=embeds.create_error_embed(
                        "Not Authorized",
                        "Only the President can end a state of emergency."
                    ),
                    ephemeral=True
                )

            embed = discord.Embed(
                title="✅ STATE OF EMERGENCY ENDED",
                description=f"President {interaction.user.mention} has ended the state of emergency.",
                color=0x2ECC71,
                timestamp=utils.datetime_now()
            )
            embed.add_field(name="📊 Summary of Actions", value=summary, inline=False)
            embed.add_field(
                name="🔄 Normal Operations Resumed",
                value="• Grand Council powers restored\n"
                      "• Constitution fully reinstated\n"
                      "• Standard procedures in effect",
                inline=False
            )

            guild_data = utils.get_guild_data(self.client.db, interaction.guild.id)
            channel = interaction.guild.get_channel(int(guild_data["voting_channel_id"]))

            await channel.send("@everyone", embed=embed)
            await interaction.response.send_message(
                embed=embeds.create_success_embed("Emergency Ended", "Normal operations have been restored."),
                ephemeral=True
            )
        except Exception as e:
            await utils.handle_interaction_error(interaction, e)

    @app_commands.command(name="emergency_action", description="[President] Take emergency action")
    @app_commands.choices(action=[
        app_commands.Choice(name="Issue Emergency Decree", value="decree"),
        app_commands.Choice(name="Dissolve Grand Council", value="dissolve"),
        app_commands.Choice(name="Remove Official", value="remove"),
    ])
    async def emergency_action(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        details: str
    ):
        try:
            if not await utils.is_eligible(self.client.db, interaction.user, interaction.guild, "president"):
                return await interaction.response.send_message(
                    embed=embeds.create_error_embed(
                        "Not Authorized",
                        "Only the President can take emergency actions."
                    ),
                    ephemeral=True
                )

            action_titles = {
                "decree": "Emergency Decree Issued",
                "dissolve": "Grand Council Dissolved",
                "remove": "Official Removed"
            }

            embed = embeds.create_emergency_embed(
                action_titles.get(action.value, "Emergency Action"),
                f"President {interaction.user.mention} has taken emergency action.",
                interaction.user,
                {"📋 Details": details}
            )

            guild_data = utils.get_guild_data(self.client.db, interaction.guild.id)
            channel = interaction.guild.get_channel(int(guild_data["voting_channel_id"]))

            await channel.send(embed=embed)
            await interaction.response.send_message(
                embed=embeds.create_success_embed("Action Confirmed", "Emergency action has been executed."),
                ephemeral=True
            )
        except Exception as e:
            await utils.handle_interaction_error(interaction, e)

    @app_commands.command(name="call_meeting", description="[President/VP] Call urgent Council meeting")
    async def call_council_meeting(self, interaction: discord.Interaction, topic: str, time: str):
        try:
            if not await self.is_president_or_vp(interaction):
                return await interaction.response.send_message(
                    embed=embeds.create_error_embed(
                        "Not Authorized",
                        "Only the President or Vice President can call Council meetings."
                    ),
                    ephemeral=True
                )

            role_title = "President" if await utils.is_eligible(self.client.db, interaction.user, interaction.guild, "president") else "Vice President"

            embed = discord.Embed(
                title="📢 URGENT COUNCIL MEETING",
                description=f"{role_title} {interaction.user.mention} has called an urgent Grand Council meeting.",
                color=0xF39C12,
                timestamp=utils.datetime_now()
            )
            embed.add_field(name="📋 Topic", value=topic, inline=False)
            embed.add_field(name="⏰ Scheduled", value=time, inline=False)
            embed.set_footer(text="All councillors are expected to attend")

            guild_data = utils.get_guild_data(self.client.db, interaction.guild.id)
            if guild_data and guild_data.get('councillor_role_id'):
                channel = interaction.guild.get_channel(int(guild_data["voting_channel_id"]))
                await channel.send(f"<@&{guild_data['councillor_role_id']}>", embed=embed)

            await interaction.response.send_message(
                embed=embeds.create_success_embed("Meeting Called", "All councillors have been notified."),
                ephemeral=True
            )
        except Exception as e:
            await utils.handle_interaction_error(interaction, e)

async def setup(client: commands.Bot) -> None:
    await client.add_cog(Executive(client))

