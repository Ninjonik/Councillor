import discord
from appwrite.query import Query
from appwrite.id import ID
import config
import utils
import embeds

class ElectionsAnnouncement(discord.ui.View):
    """View for election announcement with registration buttons"""

    def __init__(self, db_client, election_id: str):
        super().__init__(timeout=None)
        self.db = db_client
        self.election_id = election_id

    @discord.ui.button(label="Run for Council", style=discord.ButtonStyle.primary, emoji="🏛️")
    async def register_as_candidate(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Register as a candidate for Grand Council"""
        await interaction.response.defer(ephemeral=True)

        # Use the election_id stored in the view
        election_id = self.election_id

        # Check if member is old enough
        if not utils.is_member_old_enough(interaction.user):
            return await interaction.followup.send(
                embed=embeds.create_error_embed(
                    "Not Eligible",
                    f"You must have been a member for at least {config.VOTING_AGE_DAYS} days to participate in elections."
                ),
                ephemeral=True
            )

        # Check if already registered
        if await utils.check_already_registered(self.db, election_id, str(interaction.user.id)):
            return await interaction.followup.send(
                embed=embeds.create_error_embed(
                    "Already Registered",
                    "You are already registered for this election."
                ),
                ephemeral=True
            )

        # Check candidate limit
        candidate_count = self.db.list_documents(
            database_id=config.APPWRITE_DATABASE_ID,
            collection_id=config.COLLECTION_REGISTERED,
            queries=[
                Query.equal("election", election_id),
                Query.equal("candidate", True)
            ]
        )

        if candidate_count["total"] >= config.MAX_CANDIDATES:
            return await interaction.followup.send(
                embed=embeds.create_error_embed(
                    "Candidate Limit Reached",
                    f"The maximum of {config.MAX_CANDIDATES} candidates has been reached."
                ),
                ephemeral=True
            )

        # Register as candidate
        result = await utils.register_for_election(
            self.db,
            election_id,
            str(interaction.user.id),
            interaction.user.display_name,
            True
        )

        if result:
            await interaction.followup.send(
                embed=embeds.create_success_embed(
                    "Registered as Candidate",
                    "You have successfully registered to run for the Grand Council! Good luck in the election."
                ),
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                embed=embeds.create_error_embed(
                    "Registration Failed",
                    "Failed to register. Please try again or contact an administrator."
                ),
                ephemeral=True
            )

    @discord.ui.button(label="Register to Vote", style=discord.ButtonStyle.success, emoji="✅")
    async def register_as_voter(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Register as a voter"""
        await interaction.response.defer(ephemeral=True)

        # Use the election_id stored in the view
        election_id = self.election_id

        # Check if member is old enough
        if not utils.is_member_old_enough(interaction.user):
            return await interaction.followup.send(
                embed=embeds.create_error_embed(
                    "Not Eligible",
                    f"You must have been a member for at least {config.VOTING_AGE_DAYS} days to vote."
                ),
                ephemeral=True
            )

        # Check if already registered
        if await utils.check_already_registered(self.db, election_id, str(interaction.user.id)):
            return await interaction.followup.send(
                embed=embeds.create_error_embed(
                    "Already Registered",
                    "You are already registered for this election."
                ),
                ephemeral=True
            )

        # Register as voter
        result = await utils.register_for_election(
            self.db,
            election_id,
            str(interaction.user.id),
            interaction.user.display_name,
            False
        )

        if result:
            await interaction.followup.send(
                embed=embeds.create_success_embed(
                    "Registered to Vote",
                    "You have successfully registered to vote in this election!"
                ),
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                embed=embeds.create_error_embed(
                    "Registration Failed",
                    "Failed to register. Please try again or contact an administrator."
                ),
                ephemeral=True
            )


class ElectionsVoting(discord.ui.View):
    """View for voting on candidates"""

    def __init__(self, db_client, candidates: list, election_id: str):
        super().__init__(timeout=None)
        self.db = db_client
        self.candidates = candidates
        self.election_id = election_id

    def generate_buttons(self):
        """Generate voting buttons for each candidate"""
        buttons = []
        for i, candidate in enumerate(self.candidates[:config.MAX_CANDIDATES]):
            emoji = utils.generate_keycap_emoji(i + 1)
            button = discord.ui.Button(
                label=candidate['name'],
                style=discord.ButtonStyle.primary,
                emoji=emoji,
                custom_id=f"vote_{candidate['$id']}"
            )
            button.callback = self.create_vote_callback(candidate)
            buttons.append(button)
        return buttons

    def create_vote_callback(self, candidate: dict):
        """Create callback for voting button"""
        async def callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)

            # Use the election_id stored in the view instead of message.id
            election_id = self.election_id
            voter_id = str(interaction.user.id)

            # Check if user is registered to vote
            registered = self.db.list_documents(
                database_id=config.APPWRITE_DATABASE_ID,
                collection_id=config.COLLECTION_REGISTERED,
                queries=[
                    Query.equal("election", election_id),
                    Query.equal("discord_id", voter_id),
                    Query.equal("candidate", False)
                ]
            )

            if registered["total"] == 0:
                return await interaction.followup.send(
                    embed=embeds.create_error_embed(
                        "Not Registered",
                        "You must register to vote during the registration period."
                    ),
                    ephemeral=True
                )

            # Check if already voted
            if await utils.has_voted(self.db, election_id, voter_id):
                return await interaction.followup.send(
                    embed=embeds.create_error_embed(
                        "Already Voted",
                        "You have already cast your vote in this election."
                    ),
                    ephemeral=True
                )

            # Record the vote
            result = await utils.record_vote(self.db, election_id, voter_id, [candidate['$id']])

            if not result:
                return await interaction.followup.send(
                    embed=embeds.create_error_embed(
                        "Vote Failed",
                        "Failed to record your vote. Please try again."
                    ),
                    ephemeral=True
                )

            # Update candidate vote count
            try:
                # Fetch current candidate data to get the latest vote count
                current_candidate = self.db.get_document(
                    database_id=config.APPWRITE_DATABASE_ID,
                    collection_id=config.COLLECTION_REGISTERED,
                    document_id=candidate['$id']
                )

                # Increment the current vote count
                new_vote_count = current_candidate.get('votes', 0) + 1

                # Update with the new count
                self.db.update_document(
                    database_id=config.APPWRITE_DATABASE_ID,
                    collection_id=config.COLLECTION_REGISTERED,
                    document_id=candidate['$id'],
                    data={"votes": new_vote_count}
                )
            except Exception as e:
                print(f"Error updating vote count: {e}")

            await interaction.followup.send(
                embed=embeds.create_success_embed(
                    "Vote Recorded",
                    f"Your vote for **{candidate['name']}** has been recorded!\n\nThank you for participating in the democratic process."
                ),
                ephemeral=True
            )

        return callback


class ChancellorElectionAnnouncement(discord.ui.View):
    """View for chancellor election announcement with registration buttons"""

    def __init__(self, db_client, election_id: str):
        super().__init__(timeout=None)
        self.db = db_client
        self.election_id = election_id

    @discord.ui.button(label="Run for Chancellor", style=discord.ButtonStyle.primary, emoji="👑")
    async def register_as_candidate(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Register as a candidate for Chancellor"""
        await interaction.response.defer(ephemeral=True)

        # Check if user is a councillor
        if not utils.is_councillor(interaction.user):
            return await interaction.followup.send(
                embed=embeds.create_error_embed(
                    "Not Eligible",
                    "Only current Councillors can run for Chancellor."
                ),
                ephemeral=True
            )

        # Use the election_id stored in the view
        election_id = self.election_id

        # Check if already registered
        if await utils.check_already_registered(self.db, election_id, str(interaction.user.id)):
            return await interaction.followup.send(
                embed=embeds.create_error_embed(
                    "Already Registered",
                    "You are already registered for this election."
                ),
                ephemeral=True
            )

        # Check candidate limit
        candidate_count = self.db.list_documents(
            database_id=config.APPWRITE_DATABASE_ID,
            collection_id=config.COLLECTION_REGISTERED,
            queries=[
                Query.equal("election", election_id),
                Query.equal("candidate", True)
            ]
        )

        if candidate_count["total"] >= config.MAX_CANDIDATES:
            return await interaction.followup.send(
                embed=embeds.create_error_embed(
                    "Candidate Limit Reached",
                    f"The maximum of {config.MAX_CANDIDATES} candidates has been reached."
                ),
                ephemeral=True
            )

        # Register as candidate
        result = await utils.register_for_election(
            self.db,
            election_id,
            str(interaction.user.id),
            interaction.user.display_name,
            True
        )

        if result:
            await interaction.followup.send(
                embed=embeds.create_success_embed(
                    "Registered as Candidate",
                    "You have successfully registered to run for Chancellor! Good luck in the election."
                ),
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                embed=embeds.create_error_embed(
                    "Registration Failed",
                    "Failed to register. Please try again or contact an administrator."
                ),
                ephemeral=True
            )

    @discord.ui.button(label="Register to Vote", style=discord.ButtonStyle.success, emoji="✅")
    async def register_as_voter(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Register as a voter"""
        await interaction.response.defer(ephemeral=True)

        # Check if user is a councillor
        if not utils.is_councillor(interaction.user):
            return await interaction.followup.send(
                embed=embeds.create_error_embed(
                    "Not Eligible",
                    "Only current Councillors can vote in Chancellor elections."
                ),
                ephemeral=True
            )

        # Use the election_id stored in the view
        election_id = self.election_id

        # Check if already registered
        if await utils.check_already_registered(self.db, election_id, str(interaction.user.id)):
            return await interaction.followup.send(
                embed=embeds.create_error_embed(
                    "Already Registered",
                    "You are already registered for this election."
                ),
                ephemeral=True
            )

        # Register as voter
        result = await utils.register_for_election(
            self.db,
            election_id,
            str(interaction.user.id),
            interaction.user.display_name,
            False
        )

        if result:
            await interaction.followup.send(
                embed=embeds.create_success_embed(
                    "Registered to Vote",
                    "You have successfully registered to vote in this Chancellor election!"
                ),
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                embed=embeds.create_error_embed(
                    "Registration Failed",
                    "Failed to register. Please try again or contact an administrator."
                ),
                ephemeral=True
            )


class ChancellorElectionVoting(discord.ui.View):
    """View for voting on chancellor candidates"""

    def __init__(self, db_client, candidates: list, election_id: str):
        super().__init__(timeout=None)
        self.db = db_client
        self.candidates = candidates
        self.election_id = election_id

    def generate_buttons(self):
        """Generate voting buttons for each candidate"""
        buttons = []
        for i, candidate in enumerate(self.candidates[:config.MAX_CANDIDATES]):
            emoji = utils.generate_keycap_emoji(i + 1)
            button = discord.ui.Button(
                label=candidate['name'],
                style=discord.ButtonStyle.primary,
                emoji=emoji,
                custom_id=f"chancellor_vote_{candidate['$id']}"
            )
            button.callback = self.create_vote_callback(candidate)
            buttons.append(button)
        return buttons

    def create_vote_callback(self, candidate: dict):
        """Create callback for voting button"""
        async def callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)

            # Check if user is a councillor
            if not utils.is_councillor(interaction.user):
                return await interaction.followup.send(
                    embed=embeds.create_error_embed(
                        "Not Eligible",
                        "Only current Councillors can vote in Chancellor elections."
                    ),
                    ephemeral=True
                )

            # Use the election_id stored in the view instead of message.id
            election_id = self.election_id
            voter_id = str(interaction.user.id)

            # Check if user is registered to vote
            registered = self.db.list_documents(
                database_id=config.APPWRITE_DATABASE_ID,
                collection_id=config.COLLECTION_REGISTERED,
                queries=[
                    Query.equal("election", election_id),
                    Query.equal("discord_id", voter_id),
                    Query.equal("candidate", False)
                ]
            )

            if registered["total"] == 0:
                return await interaction.followup.send(
                    embed=embeds.create_error_embed(
                        "Not Registered",
                        "You must register to vote during the registration period."
                    ),
                    ephemeral=True
                )

            # Check if already voted
            if await utils.has_voted(self.db, election_id, voter_id):
                return await interaction.followup.send(
                    embed=embeds.create_error_embed(
                        "Already Voted",
                        "You have already cast your vote in this election."
                    ),
                    ephemeral=True
                )

            # Record the vote
            result = await utils.record_vote(self.db, election_id, voter_id, [candidate['$id']])

            if not result:
                return await interaction.followup.send(
                    embed=embeds.create_error_embed(
                        "Vote Failed",
                        "Failed to record your vote. Please try again."
                    ),
                    ephemeral=True
                )

            # Update candidate vote count
            try:
                # Fetch current candidate data to get the latest vote count
                current_candidate = self.db.get_document(
                    database_id=config.APPWRITE_DATABASE_ID,
                    collection_id=config.COLLECTION_REGISTERED,
                    document_id=candidate['$id']
                )

                # Increment the current vote count
                new_vote_count = current_candidate.get('votes', 0) + 1

                # Update with the new count
                self.db.update_document(
                    database_id=config.APPWRITE_DATABASE_ID,
                    collection_id=config.COLLECTION_REGISTERED,
                    document_id=candidate['$id'],
                    data={"votes": new_vote_count}
                )
            except Exception as e:
                print(f"Error updating vote count: {e}")

            await interaction.followup.send(
                embed=embeds.create_success_embed(
                    "Vote Recorded",
                    f"Your vote for **{candidate['name']}** for Chancellor has been recorded!\n\nThank you for participating."
                ),
                ephemeral=True
            )

        return callback


class ProposalVoting(discord.ui.View):
    """View for voting on proposals with buttons for anonymity"""

    def __init__(self, db_client, proposal_id: str):
        super().__init__(timeout=None)
        self.db = db_client
        self.proposal_id = proposal_id

    @discord.ui.button(label="Vote For", style=discord.ButtonStyle.success, emoji="✅")
    async def vote_for(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Vote in favor of the proposal"""
        await self._handle_vote(interaction, True)

    @discord.ui.button(label="Vote Against", style=discord.ButtonStyle.danger, emoji="❌")
    async def vote_against(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Vote against the proposal"""
        await self._handle_vote(interaction, False)

    async def _handle_vote(self, interaction: discord.Interaction, vote_for: bool):
        """Handle vote submission"""
        await interaction.response.defer(ephemeral=True)

        voter_id = str(interaction.user.id)
        proposal_id = self.proposal_id

        # Check if user is a councillor
        if not utils.is_councillor(interaction.user):
            return await interaction.followup.send(
                embed=embeds.create_error_embed(
                    "Not Authorized",
                    "Only Councillors can vote on proposals."
                ),
                ephemeral=True
            )

        # Check if already voted
        if await utils.has_voted_on_proposal(self.db, proposal_id, voter_id):
            return await interaction.followup.send(
                embed=embeds.create_error_embed(
                    "Already Voted",
                    "You have already cast your vote on this proposal."
                ),
                ephemeral=True
            )

        # Record the vote
        result = await utils.record_vote_on_proposal(self.db, proposal_id, voter_id, vote_for)

        if not result:
            return await interaction.followup.send(
                embed=embeds.create_error_embed(
                    "Vote Failed",
                    "Failed to record your vote. Please try again."
                ),
                ephemeral=True
            )

        # Update proposal vote count
        try:
            # Fetch current proposal data
            current_proposal = self.db.get_document(
                database_id=config.APPWRITE_DATABASE_ID,
                collection_id=config.COLLECTION_PROPOSALS,
                document_id=proposal_id
            )

            # Increment the appropriate vote count
            if vote_for:
                new_votes_for = current_proposal.get('votes_for', 0) + 1
                self.db.update_document(
                    database_id=config.APPWRITE_DATABASE_ID,
                    collection_id=config.COLLECTION_PROPOSALS,
                    document_id=proposal_id,
                    data={"votes_for": new_votes_for}
                )
            else:
                new_votes_against = current_proposal.get('votes_against', 0) + 1
                self.db.update_document(
                    database_id=config.APPWRITE_DATABASE_ID,
                    collection_id=config.COLLECTION_PROPOSALS,
                    document_id=proposal_id,
                    data={"votes_against": new_votes_against}
                )
        except Exception as e:
            print(f"Error updating vote count: {e}")

        vote_type = "**For**" if vote_for else "**Against**"
        await interaction.followup.send(
            embed=embeds.create_success_embed(
                "Vote Recorded",
                f"Your vote {vote_type} has been recorded anonymously.\n\nThank you for participating in the legislative process."
            ),
            ephemeral=True
        )
