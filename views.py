from appwrite.id import ID
from datetime import datetime
import discord
from appwrite.query import Query
import config
from utils import datetime_now, generate_keycap_emoji, get_guild_data, get_councillor_data, is_eligible, \
    handle_interaction_error


class CouncilDialog(discord.ui.View):
    def __init__(self, databases):
        super().__init__(timeout=None)
        self.databases = databases

    @discord.ui.button(label="Become MP!", style=discord.ButtonStyle.blurple, custom_id="co_council_member", emoji="📋")
    async def councillor(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_data = get_guild_data(self.databases, interaction.guild.id)
        if not guild_data or not guild_data.get("councillor_role_id"):
            return await interaction.response.send_message("❌ Councillor role not configured!", ephemeral=True)

        councillor_role = interaction.guild.get_role(int(guild_data["councillor_role_id"]))
        if not councillor_role:
            return await interaction.response.send_message("❌ Councillor role not found!", ephemeral=True)

        joined_at_days = (datetime.now(datetime.UTC if hasattr(datetime, 'UTC') else None) - interaction.user.joined_at).days

        if joined_at_days < config.DAYS_REQUIREMENT:
            return await interaction.response.send_message(
                f"❌ **Eligibility Requirement Not Met**\n\n"
                f"You need to be a server member for at least **{config.DAYS_REQUIREMENT} days**.\n"
                f"Current membership: **{joined_at_days} days**\n"
                f"Time remaining: **{config.DAYS_REQUIREMENT - joined_at_days} days**",
                ephemeral=True
            )

        if config.ROLE_REQUIREMENT_ID:
            req_role = interaction.guild.get_role(config.ROLE_REQUIREMENT_ID)
            if req_role and req_role not in interaction.user.roles:
                return await interaction.response.send_message(
                    f"❌ **Missing Required Role**\n\nYou need the **{req_role.name}** role to become a councillor.",
                    ephemeral=True
                )

        councillor_data = await get_councillor_data(self.databases, interaction.user.id, interaction.guild.id)
        council_id = str(interaction.guild.id) + "_c"

        if councillor_data:
            self.databases.delete_document(
                database_id=config.APPWRITE_DB_NAME,
                collection_id='councillors',
                document_id=councillor_data["$id"]
            )
            await interaction.user.remove_roles(councillor_role)

            embed = discord.Embed(
                title="👋 Left the Council",
                description=f"{interaction.user.mention} has stepped down from their position as MP.",
                color=0xE67E22
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            self.databases.create_document(
                database_id=config.APPWRITE_DB_NAME,
                collection_id='councillors',
                document_id=ID.unique(),
                data={
                    'discord_id': str(interaction.user.id),
                    'name': interaction.user.display_name,
                    'council': council_id
                }
            )
            await interaction.user.add_roles(councillor_role)

            embed = discord.Embed(
                title="🎉 Joined the Council!",
                description=f"Welcome, {interaction.user.mention}!\n\n"
                           f"You are now a Member of Parliament. You can:\n"
                           f"• Vote on legislation using `/propose`\n"
                           f"• Participate in Council debates\n"
                           f"• Help shape the future of {interaction.guild.name}",
                color=0x2ECC71
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Learn More", style=discord.ButtonStyle.gray, custom_id="co_council", emoji="📖")
    async def council(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="📚 About the Grand Council",
            description="The Grand Council is the heart of our democratic system.",
            color=0x3498DB
        )

        embed.add_field(
            name="🏛️ What is it?",
            value="A legislative body of 12 elected Members of Parliament (MPs) who vote on laws and policies.",
            inline=False
        )

        embed.add_field(
            name="⚖️ Powers",
            value="• Pass legislation (simple majority)\n"
                  "• Amend constitution (2/3 majority)\n"
                  "• Impeach officials (2/3 majority)\n"
                  "• Override Chancellor vetos (2/3 majority)",
            inline=False
        )

        embed.add_field(
            name="📅 Terms",
            value="• 3-month terms for MPs\n"
                  "• Monthly elections for 4 new seats\n"
                  "• Chancellor elected by Council",
            inline=False
        )

        embed.add_field(
            name="📜 Full Constitution",
            value="[Read the Constitution](https://docs.google.com/document/d/1f6uNX9h0NX8Ep06N74dVGsMEEqDa0I84YZp-yVvKQsg/edit)",
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

class VotingDialog(discord.ui.View):
    def __init__(self, databases):
        super().__init__(timeout=None)
        self.databases = databases

    async def handle_vote(self, interaction: discord.Interaction, stance: bool):
        if interaction.user.bot:
            return await interaction.response.send_message("❌ Bots cannot vote.", ephemeral=True)

        try:
            voting_result = self.databases.list_documents(
                database_id=config.APPWRITE_DB_NAME,
                collection_id='votings',
                queries=[Query.equal('message_id', str(interaction.message.id))]
            )

            if not voting_result["documents"]:
                return await interaction.response.send_message("❌ Voting not found.", ephemeral=True)

            voting_data = voting_result["documents"][0]

            if not await is_eligible(self.databases, interaction.user, interaction.guild, "councillor"):
                return await interaction.response.send_message(
                    "❌ **Not Eligible**\n\nOnly councillors can vote on this proposal.",
                    ephemeral=True
                )

            councillor_data = await get_councillor_data(self.databases, interaction.user.id, interaction.guild.id)
            if not councillor_data:
                return await interaction.response.send_message("❌ Councillor data not found.", ephemeral=True)

            voting_end_date = datetime.fromisoformat(voting_data['voting_end'])
            if datetime_now() > voting_end_date:
                return await interaction.response.send_message(
                    "❌ **Voting Closed**\n\nThis vote has already concluded.",
                    ephemeral=True
                )

            existing_vote = self.databases.list_documents(
                database_id=config.APPWRITE_DB_NAME,
                collection_id='votes',
                queries=[
                    Query.equal('voting', voting_data["$id"]),
                    Query.equal('councillor', councillor_data["$id"])
                ]
            )

            action = "changed"
            if existing_vote["documents"]:
                self.databases.delete_document(
                    database_id=config.APPWRITE_DB_NAME,
                    collection_id="votes",
                    document_id=existing_vote["documents"][0]["$id"]
                )
            else:
                action = "recorded"

            self.databases.create_document(
                database_id=config.APPWRITE_DB_NAME,
                collection_id='votes',
                document_id=ID.unique(),
                data={
                    "councillor": councillor_data["$id"],
                    "voting": voting_data["$id"],
                    "stance": stance
                }
            )

            vote_emoji = "✅ Yes" if stance else "❌ No"
            embed = discord.Embed(
                title=f"🗳️ Vote {action.title()}",
                description=f"Your vote has been **{action}**: {vote_emoji}",
                color=0x2ECC71 if stance else 0xE74C3C
            )
            embed.set_footer(text="You can change your vote anytime before voting closes")

            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await handle_interaction_error(interaction, e)

    @discord.ui.button(style=discord.ButtonStyle.success, custom_id="vd_yes", emoji="✅", label="Vote Yes")
    async def vd_yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_vote(interaction, True)

    @discord.ui.button(style=discord.ButtonStyle.danger, custom_id="vd_no", emoji="❎", label="Vote No")
    async def vd_no(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_vote(interaction, False)

    @discord.ui.button(style=discord.ButtonStyle.secondary, custom_id="vd_veto", emoji="⛔", label="Veto")
    async def vd_veto(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await is_eligible(self.databases, interaction.user, interaction.guild, "chancellor"):
            return await interaction.response.send_message(
                "❌ **Not Authorized**\n\nOnly the Chancellor can veto legislation.",
                ephemeral=True
            )
        await interaction.response.send_modal(VetoReason())

class VetoReason(discord.ui.Modal, title='Veto Legislation'):
    reason = discord.ui.TextInput(
        label='Reason for Veto',
        placeholder='Explain why you are vetoing this legislation...',
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        from embeds import create_error_embed
        try:
            voting = interaction.client.db.get_document(
                database_id=config.APPWRITE_DB_NAME,
                collection_id="votings",
                document_id=str(interaction.message.id)
            )

            guild_data = get_guild_data(interaction.client.db, interaction.guild.id)
            channel = interaction.guild.get_channel(int(guild_data["voting_channel_id"]))

            embed = create_error_embed(
                f"{voting['title']} - VETOED",
                f"This legislation has been vetoed by Chancellor {interaction.user.mention}"
            )
            embed.add_field(name="📝 Reason", value=self.reason.value, inline=False)
            embed.add_field(
                name="⚖️ Override Option",
                value="The Grand Council may override this veto with a 2/3 majority vote.",
                inline=False
            )

            if voting.get('proposer'):
                councillor = interaction.client.db.get_document(
                    database_id=config.APPWRITE_DB_NAME,
                    collection_id='councillors',
                    document_id=voting['proposer']
                )
                embed.set_footer(text=f"Originally proposed by {councillor['name']}")

            await channel.send(embed=embed)
            await interaction.response.send_message("✅ Legislation vetoed successfully.", ephemeral=True)
        except Exception as e:
            await handle_interaction_error(interaction, e)

class ElectionsAnnouncement(discord.ui.View):
    def __init__(self, databases):
        super().__init__(timeout=None)
        self.databases = databases

    async def handle_register(self, interaction: discord.Interaction, candidate: bool):
        election_id = str(interaction.message.id)
        user_id = str(interaction.user.id)

        existing = self.databases.list_documents(
            database_id=config.APPWRITE_DB_NAME,
            collection_id="registered",
            queries=[
                Query.equal("election", election_id),
                Query.equal("discord_id", user_id)
            ]
        )

        if existing["total"] > 0:
            return await interaction.response.send_message(
                "❌ **Already Registered**\n\nYou have already registered for this election.",
                ephemeral=True
            )

        self.databases.create_document(
            database_id=config.APPWRITE_DB_NAME,
            collection_id="registered",
            document_id=ID.unique(),
            data={
                "name": interaction.user.display_name,
                "candidate": candidate,
                "election": election_id,
                "discord_id": user_id,
                "votes": 0
            }
        )

        role_text = "candidate" if candidate else "voter"
        embed = discord.Embed(
            title="✅ Registration Successful!",
            description=f"You are now registered as a **{role_text}** in this election.",
            color=0x2ECC71
        )

        if candidate:
            embed.add_field(
                name="🚀 Next Steps",
                value="• Campaign to the community\n"
                      "• Share your vision and policies\n"
                      "• Answer questions from voters",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(style=discord.ButtonStyle.success, custom_id="ea_register", emoji="🗳️", label="Register to Vote")
    async def ea_register(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_register(interaction, False)

    @discord.ui.button(style=discord.ButtonStyle.danger, custom_id="ea_candidate", emoji="🚀", label="Run for Office")
    async def ea_candidate(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_register(interaction, True)

class ElectionsVoting(discord.ui.View):
    def __init__(self, databases, candidates):
        super().__init__(timeout=None)
        self.databases = databases
        self.candidates = candidates

    async def handle_vote(self, interaction: discord.Interaction, candidate_index: int):
        candidate = self.candidates[candidate_index]

        eligible_check = self.databases.list_documents(
            database_id=config.APPWRITE_DB_NAME,
            collection_id="registered",
            queries=[
                Query.equal("election", candidate["election"]),
                Query.equal("discord_id", str(interaction.user.id))
            ]
        )

        if eligible_check["total"] < 1:
            return await interaction.response.send_message(
                "❌ **Not Registered**\n\nYou must register to vote before the election starts.",
                ephemeral=True
            )

        voter = eligible_check["documents"][0]

        if voter["votes"] == -1:
            return await interaction.response.send_message(
                "❌ **Already Voted**\n\nYou have already cast your vote in this election.",
                ephemeral=True
            )

        if voter["candidate"]:
            return await interaction.response.send_message(
                "❌ **Candidates Cannot Vote**\n\nAs a candidate, you cannot vote in this election.",
                ephemeral=True
            )

        new_votes = (candidate.get("votes") or 0) + 1
        self.databases.update_document(
            database_id=config.APPWRITE_DB_NAME,
            collection_id="registered",
            document_id=candidate["$id"],
            data={"votes": new_votes}
        )

        self.databases.update_document(
            database_id=config.APPWRITE_DB_NAME,
            collection_id="registered",
            document_id=voter["$id"],
            data={"votes": -1}
        )

        embed = discord.Embed(
            title="🗳️ Vote Cast Successfully!",
            description=f"You voted for **{candidate['name']}**",
            color=0x2ECC71
        )
        embed.set_footer(text="Thank you for participating in democracy!")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    def generate_buttons(self):
        buttons = []
        for i, candidate in enumerate(self.candidates):
            button = discord.ui.Button(
                style=discord.ButtonStyle.primary,
                custom_id=f"vote_{i}",
                emoji=generate_keycap_emoji(i + 1),
                label=candidate['name'][:80]
            )
            button.callback = lambda interaction, idx=i: self.handle_vote(interaction, idx)
            buttons.append(button)
        return buttons


