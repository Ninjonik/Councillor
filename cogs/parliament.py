from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands
from utils import (
    is_councillor,
    get_councillor_data,
    get_all_councillors,
    has_voted_on_proposal,
    record_vote_on_proposal,
    get_guild_data,
    get_role_by_type,
    has_role
)
import utils
from embeds import (
    create_success_embed,
    create_error_embed,
    create_info_embed,
    create_voting_proposal_embed,
    create_council_info_embed,
)
import config
from appwrite.query import Query
from appwrite.id import ID

# Admin user ID - has wildcard permissions
ADMIN_USER_ID = 231105080961531905

async def is_admin_or_councillor(user: discord.Member, db_client) -> bool:
    """Check if user is admin or councillor"""
    if user.id == ADMIN_USER_ID:
        return True
    return await has_role(user, "councillor", db_client)


class Parliament(commands.Cog):
    """Grand Council legislative commands"""

    def __init__(self, client: commands.Bot):
        self.client = client

    @app_commands.command(name="council", description="View current Grand Council members")
    @app_commands.guild_only()
    async def council(self, interaction: discord.Interaction):
        """Display current Grand Council members"""
        await interaction.response.defer()

        try:
            # Get guild config
            guild_data = get_guild_data(self.client.db, interaction.guild.id)

            if not guild_data:
                await interaction.followup.send(
                    embed=create_error_embed("Setup Required", "This server hasn't been configured yet."),
                    ephemeral=True
                )
                return

            councillors = await get_all_councillors(self.client.db, interaction.guild.id)

            embed = create_info_embed("🏛️ Grand Council", "")

            # Find Chancellor
            chancellor_role = get_role_by_type(interaction.guild, guild_data, "chancellor")
            if chancellor_role and chancellor_role.members:
                chancellor_list = "\n".join([m.mention for m in chancellor_role.members])
                embed.add_field(name="👑 Chancellor", value=chancellor_list, inline=False)
            else:
                embed.add_field(name="👑 Chancellor", value="*Vacant*", inline=False)

            # Find Councillors
            if councillors:
                councillor_list = []
                for c in councillors:
                    member = interaction.guild.get_member(int(c['discord_id']))
                    if member:
                        councillor_list.append(member.mention)

                if councillor_list:
                    embed.add_field(
                        name=f"🎖️ Councillors ({len(councillor_list)}/{config.COUNCILLORS_TOTAL})",
                        value="\n".join(councillor_list),
                        inline=False
                    )
            else:
                embed.add_field(name="🎖️ Councillors", value="*None elected*", inline=False)

            # Find President and Vice President
            president_role = get_role_by_type(interaction.guild, guild_data, "president")
            if president_role and president_role.members:
                embed.add_field(name="🇺🇸 President", value=president_role.members[0].mention, inline=True)

            vp_role = get_role_by_type(interaction.guild, guild_data, "vice_president")
            if vp_role and vp_role.members:
                embed.add_field(name="🎩 Vice President", value=vp_role.members[0].mention, inline=True)

            embed.set_footer(text=f"Total Council Seats: {config.COUNCILLORS_TOTAL} | Term Length: {config.COUNCILLOR_TERM_MONTHS} months")

            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(
                embed=create_error_embed("Error", f"Failed to fetch Grand Council: {str(e)}"),
                ephemeral=True
            )

    @app_commands.command(name='propose', description="[Councillor] Create a proposal for the Council to vote on")
    @app_commands.choices(voting_type=[
        app_commands.Choice(name="⚖️ Legislation", value="legislation"),
        app_commands.Choice(name="🔵 Amendment", value="amendment"),
        app_commands.Choice(name="📜 Impeachment", value="impeachment"),
        app_commands.Choice(name="⚠️ Confidence Vote", value="confidence_vote"),
        app_commands.Choice(name="🛑 Decree", value="decree"),
        app_commands.Choice(name="🗳️ Other", value="other"),
    ])
    @app_commands.guild_only()
    async def propose(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        voting_type: app_commands.Choice[str]
    ):
        """Create a legislative proposal"""
        await interaction.response.defer(ephemeral=True)

        try:
            if not await is_admin_or_councillor(interaction.user, self.client.db):
                return await interaction.followup.send(
                    embed=create_error_embed(
                        "Not Authorized",
                        "Only councillors can propose legislation."
                    ),
                    ephemeral=True
                )

            # Get guild config
            guild_data = get_guild_data(self.client.db, interaction.guild.id)

            if not guild_data:
                await interaction.followup.send(
                    embed=create_error_embed("Setup Required", "This server hasn't been configured yet."),
                    ephemeral=True
                )
                return

            council_id = str(interaction.guild.id) + "_c"
            voting_type_data = config.VOTING_TYPES[voting_type.value]

            # Calculate voting end time
            current_date = datetime.utcnow()
            days_to_add = voting_type_data["voting_days"] + (1 if current_date.hour >= 12 else 0)
            next_day = current_date + timedelta(days=days_to_add)
            voting_end_date = datetime(next_day.year, next_day.month, next_day.day, 0, 0, 1)

            # Store proposal in database first to get the ID
            proposal_doc = self.client.db.create_document(
                database_id=config.APPWRITE_DATABASE_ID,
                collection_id=config.COLLECTION_PROPOSALS,
                document_id=ID.unique(),
                data={
                    "title": title,
                    "description": description,
                    "author_id": str(interaction.user.id),
                    "author_name": str(interaction.user),
                    "voting_type": voting_type.value,
                    "message_id": "",
                    "channel_id": str(interaction.channel.id),
                    "guild_id": str(interaction.guild.id),
                    "council": council_id,
                    "status": "active",
                    "votes_for": 0,
                    "votes_against": 0,
                    "created_at": current_date.isoformat(),
                    "end_date": voting_end_date.isoformat()
                }
            )

            # Create embed with proposal ID
            embed = create_voting_proposal_embed(
                title,
                description,
                voting_type_data,
                interaction.user,
                voting_end_date,
                proposal_doc['$id']
            )

            # Find councillor role
            councillor_role = get_role_by_type(interaction.guild, guild_data, "councillor")

            # Import the ProposalVoting view
            from views import ProposalVoting

            # Send to current channel with voting buttons
            message = await interaction.channel.send(
                content=f"<@&{councillor_role.id}>" if councillor_role else None,
                embed=embed,
                view=ProposalVoting(self.client.db, proposal_doc['$id'])
            )

            # Update proposal with message_id
            self.client.db.update_document(
                database_id=config.APPWRITE_DATABASE_ID,
                collection_id=config.COLLECTION_PROPOSALS,
                document_id=proposal_doc['$id'],
                data={"message_id": str(message.id)}
            )

            await interaction.followup.send(
                embed=create_success_embed(
                    "Proposal Created",
                    f"Your proposal **{title}** has been posted for Council voting.\n\n**Proposal ID:** `{proposal_doc['$id']}`"
                ),
                ephemeral=True
            )

        except Exception as e:
            await interaction.followup.send(
                embed=create_error_embed("Error", f"Failed to create proposal: {str(e)}"),
                ephemeral=True
            )

    @app_commands.command(name='vote_status', description="[Councillor] Check the vote count for a proposal")
    @app_commands.describe(proposal_id="The ID of the proposal to check")
    @app_commands.guild_only()
    async def vote_status(self, interaction: discord.Interaction, proposal_id: str):
        """Check vote count for a proposal"""
        await interaction.response.defer(ephemeral=True)

        try:
            if not await is_admin_or_councillor(interaction.user, self.client.db):
                return await interaction.followup.send(
                    embed=create_error_embed(
                        "Not Authorized",
                        "Only councillors can check vote status."
                    ),
                    ephemeral=True
                )

            # Fetch proposal
            try:
                proposal = self.client.db.get_document(
                    database_id=config.APPWRITE_DATABASE_ID,
                    collection_id=config.COLLECTION_PROPOSALS,
                    document_id=proposal_id
                )
            except Exception:
                return await interaction.followup.send(
                    embed=create_error_embed(
                        "Not Found",
                        f"No proposal found with ID: `{proposal_id}`"
                    ),
                    ephemeral=True
                )

            votes_for = proposal.get('votes_for', 0)
            votes_against = proposal.get('votes_against', 0)
            total_votes = votes_for + votes_against

            voting_type_data = config.VOTING_TYPES.get(proposal.get('voting_type', 'other'))
            required_percentage = voting_type_data['required_percentage']

            percentage = (votes_for / total_votes * 100) if total_votes > 0 else 0
            passing = percentage >= (required_percentage * 100)

            embed = discord.Embed(
                title=f"📊 Vote Status",
                description=f"## {proposal.get('title', 'Unknown Proposal')}\n\n"
                            f"### Current Results\n"
                            f"**✅ For:** {votes_for} votes\n"
                            f"**❌ Against:** {votes_against} votes\n"
                            f"**📊 Total:** {total_votes} votes\n\n"
                            f"### Analysis\n"
                            f"**Current Approval:** {percentage:.1f}%\n"
                            f"**Required Approval:** {int(required_percentage * 100)}%\n"
                            f"**Status:** {'✅ Currently Passing' if passing else '❌ Currently Failing'}\n\n"
                            f"**Proposal Status:** {proposal.get('status', 'unknown').title()}",
                color=0x2ECC71 if passing else 0xE74C3C,
                timestamp=utils.datetime_now()
            )

            embed.set_footer(text=f"Proposal ID: {proposal_id}")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(
                embed=create_error_embed("Error", f"Failed to fetch vote status: {str(e)}"),
                ephemeral=True
            )

    @app_commands.command(name='conclude_vote', description="[Councillor] Conclude a proposal and finalize results")
    @app_commands.describe(proposal_id="The ID of the proposal to conclude")
    @app_commands.guild_only()
    async def conclude_vote(self, interaction: discord.Interaction, proposal_id: str):
        """Conclude a proposal vote"""
        await interaction.response.defer()

        try:
            if not await is_admin_or_councillor(interaction.user, self.client.db):
                return await interaction.followup.send(
                    embed=create_error_embed(
                        "Not Authorized",
                        "Only councillors can conclude votes."
                    ),
                    ephemeral=True
                )

            # Fetch proposal
            try:
                proposal = self.client.db.get_document(
                    database_id=config.APPWRITE_DATABASE_ID,
                    collection_id=config.COLLECTION_PROPOSALS,
                    document_id=proposal_id
                )
            except Exception:
                return await interaction.followup.send(
                    embed=create_error_embed(
                        "Not Found",
                        f"No proposal found with ID: `{proposal_id}`"
                    ),
                    ephemeral=True
                )

            if proposal.get('status') != 'active':
                return await interaction.followup.send(
                    embed=create_error_embed(
                        "Already Concluded",
                        "This proposal has already been concluded."
                    ),
                    ephemeral=True
                )

            votes_for = proposal.get('votes_for', 0)
            votes_against = proposal.get('votes_against', 0)
            total_votes = votes_for + votes_against

            voting_type_data = config.VOTING_TYPES.get(proposal.get('voting_type', 'other'))
            required_percentage = voting_type_data['required_percentage']

            percentage = (votes_for / total_votes * 100) if total_votes > 0 else 0
            passed = percentage >= (required_percentage * 100)

            # Update proposal status
            self.client.db.update_document(
                database_id=config.APPWRITE_DATABASE_ID,
                collection_id=config.COLLECTION_PROPOSALS,
                document_id=proposal_id,
                data={"status": "passed" if passed else "failed"}
            )

            # Create results embed
            result_embed = discord.Embed(
                title=f"{'✅ Proposal Passed' if passed else '❌ Proposal Failed'}",
                description=f"## {proposal.get('title')}\n\n"
                            f"{proposal.get('description', '')[:500]}{'...' if len(proposal.get('description', '')) > 500 else ''}\n\n"
                            f"### Final Results\n"
                            f"**✅ For:** {votes_for} votes\n"
                            f"**❌ Against:** {votes_against} votes\n"
                            f"**📊 Total:** {total_votes} votes\n\n"
                            f"**Final Approval:** {percentage:.1f}% (needed {int(required_percentage * 100)}%)",
                color=0x2ECC71 if passed else 0xE74C3C,
                timestamp=utils.datetime_now()
            )

            result_embed.set_footer(text=f"Proposed by {proposal.get('author_name')} • ID: {proposal_id}")

            await interaction.channel.send(embed=result_embed)

            await interaction.followup.send(
                embed=create_success_embed(
                    "Vote Concluded",
                    f"The proposal has been concluded. Result: **{'Passed' if passed else 'Failed'}**"
                ),
                ephemeral=True
            )

        except Exception as e:
            await interaction.followup.send(
                embed=create_error_embed("Error", f"Failed to conclude vote: {str(e)}"),
                ephemeral=True
            )
