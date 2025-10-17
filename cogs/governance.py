import discord
from discord import app_commands
from discord.ext import commands
from appwrite.id import ID
from appwrite.query import Query
from datetime import datetime, timedelta
import config
import utils
import embeds
import views

class Governance(commands.Cog):
    """Member and Councillor governance commands"""

    def __init__(self, client: commands.Bot):
        self.client = client

    @app_commands.command(name="council", description="Learn about and join the Grand Council")
    async def council(self, interaction: discord.Interaction):
        try:
            req_role = interaction.guild.get_role(config.ROLE_REQUIREMENT_ID) if config.ROLE_REQUIREMENT_ID else None
            role_status = '✅' if not req_role or req_role in interaction.user.roles else '❌'

            joined_at_days = (datetime.now(datetime.UTC if hasattr(datetime, 'UTC') else None) - interaction.user.joined_at).days
            joined_status = '✅' if joined_at_days >= config.DAYS_REQUIREMENT else '❌'

            embed = discord.Embed(
                title="🏛️ The Grand Council",
                description=f"The Grand Council is the legislative heart of **{interaction.guild.name}**. "
                           f"As a Member of Parliament (MP), you'll vote on laws, policies, and the future direction of our community.",
                color=0x2ECC71
            )

            if interaction.guild.icon:
                embed.set_thumbnail(url=interaction.guild.icon.url)

            embed.add_field(
                name="📋 How to Join",
                value='Click the **"Become MP!"** button below to join the Council.',
                inline=False
            )

            embed.add_field(
                name="✅ Requirements",
                value=f"{joined_status} Be a member for {config.DAYS_REQUIREMENT}+ days (you: {joined_at_days} days)\n"
                      f"{role_status} No major punishments in the last 6 months\n"
                      f"{'✅' if not config.ROLE_REQUIREMENT_ID else role_status} {f'Have the {req_role.name} role' if req_role else 'No special role required'}",
                inline=False
            )

            embed.add_field(
                name="⚖️ What You Can Do",
                value="• Vote on legislation and amendments\n"
                      "• Propose new laws and policies\n"
                      "• Participate in debates and discussions\n"
                      "• Help elect the Chancellor",
                inline=False
            )

            embed.set_footer(text="Democracy in action! 🗳️")

            await interaction.response.send_message(
                embed=embed,
                ephemeral=True,
                view=views.CouncilDialog(self.client.db)
            )
        except Exception as e:
            await utils.handle_interaction_error(interaction, e)

    @app_commands.command(name="info", description="View current council members and leadership")
    async def info(self, interaction: discord.Interaction):
        try:
            guild_data = utils.get_guild_data(self.client.db, interaction.guild.id)

            if not guild_data:
                return await interaction.response.send_message(
                    embed=embeds.create_error_embed(
                        "Configuration Error",
                        "This server hasn't been configured yet. Contact an administrator."
                    ),
                    ephemeral=True
                )

            council_id = str(interaction.guild.id) + "_c"

            councillors_result = self.client.db.list_documents(
                database_id=config.APPWRITE_DB_NAME,
                collection_id="councillors",
                queries=[Query.equal("council", council_id)]
            )

            councillors = councillors_result["documents"]
            council_members = []
            chancellor = "None appointed"

            if guild_data.get("chancellor_role_id"):
                chancellor_role = interaction.guild.get_role(int(guild_data["chancellor_role_id"]))
                if chancellor_role:
                    for member in interaction.guild.members:
                        if chancellor_role in member.roles:
                            chancellor = member.mention
                            break

            for councillor in councillors:
                member = interaction.guild.get_member(int(councillor['discord_id']))
                if member:
                    council_members.append(member.mention)

            embed = embeds.create_council_info_embed(
                interaction.guild,
                chancellor,
                council_members
            )

            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await utils.handle_interaction_error(interaction, e)

    @app_commands.command(name='propose', description="Create a proposal for the Council to vote on")
    @app_commands.choices(voting_type=[
        app_commands.Choice(name="⚖️ Legislation", value="legislation"),
        app_commands.Choice(name="🔵 Amendment", value="amendment"),
        app_commands.Choice(name="📜 Impeachment", value="impeachment"),
        app_commands.Choice(name="⚠️ Confidence Vote", value="confidence_vote"),
        app_commands.Choice(name="🛑 Decree", value="decree"),
        app_commands.Choice(name="🗳️ Other", value="other"),
    ])
    async def propose(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        voting_type: app_commands.Choice[str]
    ):
        try:
            if not await utils.is_eligible(self.client.db, interaction.user, interaction.guild, "councillor"):
                return await interaction.response.send_message(
                    embed=embeds.create_error_embed(
                        "Not Authorized",
                        "Only councillors can propose legislation."
                    ),
                    ephemeral=True
                )

            council_id = str(interaction.guild.id) + "_c"
            guild_data = utils.get_guild_data(self.client.db, interaction.guild.id)

            if not guild_data or not guild_data.get("voting_channel_id"):
                return await interaction.response.send_message(
                    embed=embeds.create_error_embed(
                        "Configuration Error",
                        "Voting channel not configured. Contact an administrator."
                    ),
                    ephemeral=True
                )

            voting_type_data = utils.voting_types[voting_type.value]

            current_date = utils.datetime_now()
            days_to_add = voting_type_data["voting_days"] + (1 if current_date.hour >= 12 else 0)
            next_day = current_date + timedelta(days=days_to_add)
            voting_end_date = datetime(next_day.year, next_day.month, next_day.day, 0, 0, 1, tzinfo=current_date.tzinfo)

            embed = embeds.create_voting_embed(
                title,
                description,
                voting_type_data,
                interaction.user,
                voting_end_date
            )

            channel = interaction.guild.get_channel(int(guild_data["voting_channel_id"]))
            message = await channel.send(
                f"<@&{guild_data['councillor_role_id']}>",
                embed=embed,
                view=views.VotingDialog(self.client.db)
            )

            councillor_data = await utils.get_councillor_data(self.client.db, interaction.user.id, interaction.guild.id)
            if not councillor_data:
                return await interaction.response.send_message(
                    embed=embeds.create_error_embed("Error", "Councillor data not found."),
                    ephemeral=True
                )

            new_voting = self.client.db.create_document(
                database_id=config.APPWRITE_DB_NAME,
                collection_id='votings',
                document_id=str(message.id),
                data={
                    "type": voting_type.value,
                    "status": "voting",
                    "voting_end": voting_end_date.isoformat(),
                    "message_id": str(message.id),
                    "title": title,
                    "description": description,
                    "council": council_id,
                    "proposer": councillor_data["$id"],
                }
            )

            embed.set_footer(text=f"Vote ends: {voting_end_date.strftime('%d.%m.%Y %H:%M')} UTC | ID: {new_voting['$id']}")
            await message.edit(embed=embed)

            await interaction.response.send_message(
                embed=embeds.create_success_embed(
                    "Proposal Submitted",
                    f"Your proposal has been posted in {channel.mention} for Council vote."
                ),
                ephemeral=True
            )
        except Exception as e:
            await utils.handle_interaction_error(interaction, e)

    @app_commands.command(name="voting_status", description="Check the current status of a vote")
    async def voting_status(self, interaction: discord.Interaction, voting_message_id: str):
        try:
            voting = self.client.db.get_document(
                database_id=config.APPWRITE_DB_NAME,
                collection_id='votings',
                document_id=voting_message_id
            )

            votes_result = self.client.db.list_documents(
                database_id=config.APPWRITE_DB_NAME,
                collection_id='votes',
                queries=[Query.equal('voting', voting['$id'])]
            )

            votes = votes_result["documents"]
            positive_votes = sum(1 for v in votes if v["stance"])
            negative_votes = len(votes) - positive_votes

            voting_type_data = utils.voting_types.get(voting["type"])
            required_percentage = voting_type_data["required_percentage"] if voting_type_data else 0.5

            current_percentage = (positive_votes / len(votes)) if len(votes) > 0 else 0

            status_emoji = "🟢" if voting["status"] == "voting" else "🔴"

            embed = embeds.create_info_embed(
                f"{status_emoji} Voting Status",
                f"**{voting['title']}**\n\n{voting.get('description', '')[:200]}",
                0x3498DB
            )

            embed.add_field(name="✅ For", value=str(positive_votes), inline=True)
            embed.add_field(name="❌ Against", value=str(negative_votes), inline=True)
            embed.add_field(name="📊 Total", value=str(len(votes)), inline=True)

            embed.add_field(
                name="📈 Progress",
                value=f"{current_percentage*100:.1f}% (need {required_percentage*100:.0f}%)",
                inline=False
            )

            embed.add_field(name="Status", value=voting["status"].title(), inline=True)

            if voting.get("voting_end"):
                end_date = datetime.fromisoformat(voting["voting_end"])
                embed.add_field(
                    name="⏰ Ends",
                    value=f"<t:{int(end_date.timestamp())}:R>",
                    inline=True
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await utils.handle_interaction_error(interaction, e, "❌ Voting not found or error occurred")

async def setup(client: commands.Bot) -> None:
    await client.add_cog(Governance(client))

