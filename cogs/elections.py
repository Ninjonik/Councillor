import discord
from discord import app_commands
from discord.ext import commands
from appwrite.id import ID
from appwrite.query import Query
from datetime import datetime
import config
import utils
import embeds
import views

# Admin user ID - has wildcard permissions
ADMIN_USER_ID = 231105080961531905

def is_admin_or_authorized(user: discord.Member, role_check) -> bool:
    """Check if user is admin or has the required role"""
    return user.id == ADMIN_USER_ID or role_check

class Elections(commands.Cog):
    """Election management for Grand Council seats"""

    def __init__(self, client: commands.Bot):
        self.client = client

    @app_commands.command(name='elections', description="[President/VP] Manage Grand Council elections")
    @app_commands.choices(action=[
        app_commands.Choice(name="📢 Announce Election", value="announce"),
        app_commands.Choice(name="🗳️ Start Voting", value="start"),
        app_commands.Choice(name="🏆 Conclude & Count Votes", value="conclude"),
    ])
    @app_commands.describe(
        action="What action to perform",
        start="Format: DD.MM.YYYY HH:MM (UTC) - Example: 24.12.2025 23:56",
        end="Format: DD.MM.YYYY HH:MM (UTC) - Example: 31.12.2025 23:56",
        announcement_channel="Channel to post announcement (defaults to current channel)",
        ping_everyone="Whether to ping @everyone"
    )
    async def elections(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        start: str = None,
        end: str = None,
        announcement_channel: discord.TextChannel = None,
        ping_everyone: bool = False
    ):
        eligible = is_admin_or_authorized(
            interaction.user,
            await utils.is_eligible(self.client.db, interaction.user, interaction.guild, "president") or
            await utils.is_eligible(self.client.db, interaction.user, interaction.guild, "vice_president")
        )

        if not eligible:
            return await interaction.response.send_message(
                embed=embeds.create_error_embed(
                    "Not Authorized",
                    "Only the President or Vice President can manage elections."
                ),
                ephemeral=True
            )

        if not announcement_channel:
            announcement_channel = interaction.channel

        action_value = action.value
        council_id = str(interaction.guild.id) + "_c"

        start_datetime = utils.convert_datetime_from_str(start) if start else None
        end_datetime = utils.convert_datetime_from_str(end) if end else None

        if action_value == "announce":
            await self.announce_election(interaction, council_id, start_datetime, end_datetime, announcement_channel, ping_everyone)
        elif action_value == "start":
            await self.start_election(interaction, council_id, announcement_channel, ping_everyone)
        elif action_value == "conclude":
            await self.conclude_election(interaction, council_id, announcement_channel, ping_everyone)

    @app_commands.command(name='chancellor_election', description="[President/VP] Manage Chancellor elections")
    @app_commands.choices(action=[
        app_commands.Choice(name="📢 Announce Chancellor Election", value="announce"),
        app_commands.Choice(name="🗳️ Start Voting", value="start"),
        app_commands.Choice(name="🏆 Conclude & Elect Chancellor", value="conclude"),
    ])
    @app_commands.describe(
        action="What action to perform",
        start="Format: DD.MM.YYYY HH:MM (UTC) - Example: 24.12.2025 23:56",
        end="Format: DD.MM.YYYY HH:MM (UTC) - Example: 31.12.2025 23:56",
        announcement_channel="Channel to post announcement (defaults to current channel)"
    )
    async def chancellor_election(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        start: str = None,
        end: str = None,
        announcement_channel: discord.TextChannel = None
    ):
        eligible = is_admin_or_authorized(
            interaction.user,
            await utils.is_eligible(self.client.db, interaction.user, interaction.guild, "president") or
            await utils.is_eligible(self.client.db, interaction.user, interaction.guild, "vice_president")
        )

        if not eligible:
            return await interaction.response.send_message(
                embed=embeds.create_error_embed(
                    "Not Authorized",
                    "Only the President or Vice President can manage Chancellor elections."
                ),
                ephemeral=True
            )

        if not announcement_channel:
            announcement_channel = interaction.channel

        action_value = action.value
        council_id = str(interaction.guild.id) + "_c"

        start_datetime = utils.convert_datetime_from_str(start) if start else None
        end_datetime = utils.convert_datetime_from_str(end) if end else None

        if action_value == "announce":
            await self.announce_chancellor_election(interaction, council_id, start_datetime, end_datetime, announcement_channel)
        elif action_value == "start":
            await self.start_chancellor_election(interaction, council_id, announcement_channel)
        elif action_value == "conclude":
            await self.conclude_chancellor_election(interaction, council_id, announcement_channel)

    async def announce_election(self, interaction, council_id, start_datetime, end_datetime, channel, ping_everyone):
        if not start_datetime or not end_datetime:
            return await interaction.response.send_message(
                embed=embeds.create_error_embed(
                    "Invalid Date Format",
                    "Please provide both start and end dates in format: DD.MM.YYYY HH:MM\n"
                    "Example: 24.12.2025 23:56"
                ),
                ephemeral=True
            )

        check_res = self.client.db.list_documents(
            database_id=config.APPWRITE_DB_NAME,
            collection_id=config.COLLECTION_VOTINGS,
            queries=[
                Query.equal("status", "pending"),
                Query.equal("council", council_id),
            ]
        )
        if check_res["total"] > 0:
            return await interaction.response.send_message(
                embed=embeds.create_error_embed(
                    "Election Already Exists",
                    "There is already a pending election. Please conclude or cancel it first."
                ),
                ephemeral=True
            )

        embed = embeds.create_election_announcement_embed(
            interaction.guild,
            start_datetime,
            end_datetime
        )

        # Create election document FIRST with Appwrite-generated ID
        councillor_data = await utils.get_councillor_data(self.client.db, interaction.user.id, interaction.guild.id)
        proposer_id = councillor_data["$id"] if councillor_data else None

        election_doc = self.client.db.create_document(
            database_id=config.APPWRITE_DB_NAME,
            collection_id=config.COLLECTION_VOTINGS,
            document_id=ID.unique(),
            data={
                "type": "election",
                "status": "pending",
                "voting_end": end_datetime.isoformat(),
                "voting_start": start_datetime.isoformat(),
                "message_id": "",  # Will update after message is sent
                "title": "Grand Council Elections",
                "council": council_id,
                "proposer": proposer_id,
            }
        )

        # Now send message with the view
        message = await channel.send(
            content="@everyone" if ping_everyone else None,
            embed=embed,
            view=views.ElectionsAnnouncement(self.client.db, election_doc["$id"])
        )

        # Update with message_id for reference only
        self.client.db.update_document(
            database_id=config.APPWRITE_DB_NAME,
            collection_id=config.COLLECTION_VOTINGS,
            document_id=election_doc["$id"],
            data={"message_id": str(message.id)}
        )

        await interaction.response.send_message(
            embed=embeds.create_success_embed(
                "Elections Announced",
                f"Election announcement has been posted in {channel.mention}.\n"
                f"Campaign period is now open until voting begins."
            ),
            ephemeral=True
        )

    async def start_election(self, interaction, council_id, channel, ping_everyone):
        election_query = self.client.db.list_documents(
            database_id=config.APPWRITE_DB_NAME,
            collection_id=config.COLLECTION_VOTINGS,
            queries=[
                Query.equal("status", "pending"),
                Query.equal("council", council_id),
                Query.order_desc("$updatedAt"),
                Query.limit(1)
            ]
        )
        if election_query["total"] != 1:
            return await interaction.response.send_message(
                embed=embeds.create_error_embed(
                    "No Election Found",
                    "There is no pending election to start. Please announce one first."
                ),
                ephemeral=True
            )

        election = election_query["documents"][0]
        registered_query = self.client.db.list_documents(
            database_id=config.APPWRITE_DB_NAME,
            collection_id=config.COLLECTION_REGISTERED,
            queries=[Query.equal("election", election["$id"])]
        )
        registered = registered_query["documents"]

        candidates = [r for r in registered if r["candidate"]][:config.MAX_CANDIDATES]
        voters = [r for r in registered if not r["candidate"]]

        if not candidates:
            return await interaction.response.send_message(
                embed=embeds.create_error_embed(
                    "No Candidates",
                    "Cannot start election with no candidates. Please wait for candidates to register."
                ),
                ephemeral=True
            )

        embed = embeds.create_voting_embed(
            interaction.guild,
            election,
            candidates,
            voters
        )

        # Pass the election_id to the view
        view = views.ElectionsVoting(self.client.db, candidates, election["$id"])
        for button in view.generate_buttons():
            view.add_item(button)

        message = await channel.send(
            content="@everyone" if ping_everyone else None,
            embed=embed,
            view=view
        )

        self.client.db.update_document(
            database_id=config.APPWRITE_DB_NAME,
            collection_id=config.COLLECTION_VOTINGS,
            document_id=str(election['$id']),
            data={
                "status": "ongoing",
                "message_id": str(message.id),
                "proposer": None,
                "council": council_id,
            }
        )

        await interaction.response.send_message(
            embed=embeds.create_success_embed(
                "Voting Started",
                f"Election voting has begun in {channel.mention}.\n"
                f"**{len(candidates)}** candidates • **{len(voters)}** registered voters"
            ),
            ephemeral=True
        )

    async def conclude_election(self, interaction, council_id, channel, ping_everyone):
        election_query = self.client.db.list_documents(
            database_id=config.APPWRITE_DB_NAME,
            collection_id=config.COLLECTION_VOTINGS,
            queries=[
                Query.equal("status", "ongoing"),
                Query.equal("council", council_id),
                Query.order_desc("$updatedAt"),
                Query.limit(1)
            ]
        )
        if election_query["total"] != 1:
            return await interaction.response.send_message(
                embed=embeds.create_error_embed(
                    "No Active Election",
                    "There is no ongoing election to conclude."
                ),
                ephemeral=True
            )

        election = election_query["documents"][0]

        current_councillors_query = self.client.db.list_documents(
            database_id=config.APPWRITE_DB_NAME,
            collection_id=config.COLLECTION_COUNCILLORS,
            queries=[Query.equal("council", council_id)]
        )
        current_count = len(current_councillors_query["documents"])

        winners_to_select = max(config.MIN_NEW_COUNCILLORS, min(config.MAX_CANDIDATES, config.COUNCILLORS_TOTAL - current_count))

        winners_query = self.client.db.list_documents(
            database_id=config.APPWRITE_DB_NAME,
            collection_id=config.COLLECTION_REGISTERED,
            queries=[
                Query.equal("election", election["$id"]),
                Query.equal("candidate", True),
                Query.order_desc("votes"),
                Query.limit(winners_to_select),
            ]
        )
        winners = winners_query["documents"]

        if not winners:
            return await interaction.response.send_message(
                embed=embeds.create_error_embed(
                    "No Results",
                    "Cannot conclude election - no votes were cast."
                ),
                ephemeral=True
            )

        embed = embeds.create_results_embed(interaction.guild, winners)

        await channel.send(content="@everyone" if ping_everyone else None, embed=embed)

        self.client.db.update_document(
            database_id=config.APPWRITE_DB_NAME,
            collection_id=config.COLLECTION_VOTINGS,
            document_id=str(election['$id']),
            data={"status": "concluded", "council": council_id}
        )

        guild_data = utils.get_guild_data(self.client.db, interaction.guild.id)
        councillor_role = interaction.guild.get_role(int(guild_data["councillor_role_id"])) if guild_data and guild_data.get("councillor_role_id") else None
        chancellor_role = interaction.guild.get_role(int(guild_data["chancellor_role_id"])) if guild_data and guild_data.get("chancellor_role_id") else None

        # Remove oldest councillors if necessary
        if current_count > (config.COUNCILLORS_TOTAL - len(winners)):
            to_remove_count = min(current_count + len(winners) - config.COUNCILLORS_TOTAL, current_count)
            if to_remove_count > 0:
                to_delete_query = self.client.db.list_documents(
                    database_id=config.APPWRITE_DB_NAME,
                    collection_id=config.COLLECTION_COUNCILLORS,
                    queries=[
                        Query.equal("council", council_id),
                        Query.limit(to_remove_count),
                        Query.order_asc("$createdAt")
                    ]
                )
                to_delete = to_delete_query["documents"]

                for old_councillor in to_delete:
                    try:
                        self.client.db.delete_document(
                            database_id=config.APPWRITE_DB_NAME,
                            collection_id=config.COLLECTION_COUNCILLORS,
                            document_id=str(old_councillor["$id"])
                        )
                        old_member = interaction.guild.get_member(int(old_councillor["discord_id"]))
                        if old_member and councillor_role:
                            await old_member.remove_roles(councillor_role, reason="Term ended")
                            if chancellor_role and chancellor_role in old_member.roles:
                                await old_member.remove_roles(chancellor_role, reason="Term ended")
                    except Exception as e:
                        print(f"Error removing councillor: {e}")

        # Add new councillors
        added_count = 0
        for winner in winners:
            try:
                self.client.db.create_document(
                    database_id=config.APPWRITE_DB_NAME,
                    collection_id=config.COLLECTION_COUNCILLORS,
                    document_id=ID.unique(),
                    data={
                        "name": winner["name"],
                        "discord_id": winner["discord_id"],
                        "council": council_id,
                    }
                )
                winner_member = interaction.guild.get_member(int(winner["discord_id"]))
                if winner_member and councillor_role:
                    await winner_member.add_roles(councillor_role, reason="Elected to Grand Council")
                    added_count += 1
            except Exception as e:
                print(f"Error adding councillor: {e}")

        await interaction.response.send_message(
            embed=embeds.create_success_embed(
                "Election Concluded",
                f"**{len(winners)}** new councillors have been elected and assigned roles.\n"
                f"Results have been posted in {channel.mention}."
            ),
            ephemeral=True
        )

    async def announce_chancellor_election(self, interaction, council_id, start_datetime, end_datetime, channel):
        if not start_datetime or not end_datetime:
            return await interaction.response.send_message(
                embed=embeds.create_error_embed(
                    "Invalid Date Format",
                    "Please provide both start and end dates in format: DD.MM.YYYY HH:MM\n"
                    "Example: 24.12.2025 23:56"
                ),
                ephemeral=True
            )

        check_res = self.client.db.list_documents(
            database_id=config.APPWRITE_DB_NAME,
            collection_id=config.COLLECTION_VOTINGS,
            queries=[
                Query.equal("status", "pending"),
                Query.equal("type", "chancellor_election"),
                Query.equal("council", council_id),
            ]
        )
        if check_res["total"] > 0:
            return await interaction.response.send_message(
                embed=embeds.create_error_embed(
                    "Election Already Exists",
                    "There is already a pending Chancellor election."
                ),
                ephemeral=True
            )

        embed = discord.Embed(
            title="👑 Chancellor Election Announced!",
            description=f"**Attention, Councillors!**\n\n"
                       f"An election for Chancellor has been announced. "
                       f"**Only current Councillors** can run for and vote in this election.\n\n"
                       f"## 🗳️ Election Timeline\n"
                       f"### 📝 **Registration Period:** Now until voting begins\n"
                       f"### 🗳️ **Voting Period:** <t:{int(start_datetime.timestamp())}:F> to <t:{int(end_datetime.timestamp())}:F>\n\n"
                       f"**How to Participate:**\n"
                       f"• Click '👑 Run for Chancellor' below to register as a candidate\n"
                       f"• Click '✅ Register to Vote' below to register as a voter\n"
                       f"• Only Councillors can participate",
            colour=0x9B59B6,
            timestamp=utils.datetime_now()
        )
        embed.set_footer(text="Chancellor Election • Councillors Only")

        # Create election document FIRST
        election_doc = self.client.db.create_document(
            database_id=config.APPWRITE_DB_NAME,
            collection_id=config.COLLECTION_VOTINGS,
            document_id=ID.unique(),
            data={
                "type": "chancellor_election",
                "status": "pending",
                "voting_end": end_datetime.isoformat(),
                "voting_start": start_datetime.isoformat(),
                "message_id": "",
                "title": "Chancellor Election",
                "council": council_id,
                "proposer": None,
            }
        )

        # Send message with view
        message = await channel.send(
            embed=embed,
            view=views.ChancellorElectionAnnouncement(self.client.db, election_doc["$id"])
        )

        # Update with message_id
        self.client.db.update_document(
            database_id=config.APPWRITE_DB_NAME,
            collection_id=config.COLLECTION_VOTINGS,
            document_id=election_doc["$id"],
            data={"message_id": str(message.id)}
        )

        await interaction.response.send_message(
            embed=embeds.create_success_embed(
                "Chancellor Election Announced",
                f"Chancellor election has been posted in {channel.mention}.\n"
                f"Campaign period is now open until voting begins."
            ),
            ephemeral=True
        )

    async def start_chancellor_election(self, interaction, council_id, channel):
        election_query = self.client.db.list_documents(
            database_id=config.APPWRITE_DB_NAME,
            collection_id=config.COLLECTION_VOTINGS,
            queries=[
                Query.equal("status", "pending"),
                Query.equal("type", "chancellor_election"),
                Query.equal("council", council_id),
                Query.order_desc("$updatedAt"),
                Query.limit(1)
            ]
        )
        if election_query["total"] != 1:
            return await interaction.response.send_message(
                embed=embeds.create_error_embed(
                    "No Election Found",
                    "There is no pending Chancellor election to start."
                ),
                ephemeral=True
            )

        election = election_query["documents"][0]
        registered_query = self.client.db.list_documents(
            database_id=config.APPWRITE_DB_NAME,
            collection_id=config.COLLECTION_REGISTERED,
            queries=[Query.equal("election", election["$id"])]
        )
        registered = registered_query["documents"]

        candidates = [r for r in registered if r["candidate"]][:config.MAX_CANDIDATES]
        voters = [r for r in registered if not r["candidate"]]

        if not candidates:
            return await interaction.response.send_message(
                embed=embeds.create_error_embed(
                    "No Candidates",
                    "Cannot start election with no candidates."
                ),
                ephemeral=True
            )

        embed = discord.Embed(
            title="🗳️ Chancellor Election - Voting Now Open",
            description=f"**Councillors, cast your votes!**\n\n"
                       f"The voting period has begun for the new Chancellor. "
                       f"Please review the candidates below and cast your vote.\n\n"
                       f"**{len(candidates)} candidate{'s' if len(candidates) != 1 else ''}** • "
                       f"**{len(voters)} registered voter{'s' if len(voters) != 1 else ''}**\n\n"
                       f"⏰ **Voting Period**\n"
                       f"From <t:{int(datetime.fromisoformat(election['voting_start']).timestamp())}:F>\n"
                       f"To <t:{int(datetime.fromisoformat(election['voting_end']).timestamp())}:F>",
            colour=0x9B59B6,
            timestamp=utils.datetime_now()
        )

        for i, candidate in enumerate(candidates):
            emoji = utils.generate_keycap_emoji(i + 1)
            embed.add_field(
                name=f"{emoji} {candidate['name']}",
                value="Running for Chancellor",
                inline=True
            )

        embed.set_footer(text="Click a button below to cast your vote • Councillors only")

        # Pass the election_id to the view
        view = views.ChancellorElectionVoting(self.client.db, candidates, election["$id"])
        for button in view.generate_buttons():
            view.add_item(button)

        message = await channel.send(embed=embed, view=view)

        self.client.db.update_document(
            database_id=config.APPWRITE_DB_NAME,
            collection_id=config.COLLECTION_VOTINGS,
            document_id=election['$id'],
            data={
                "status": "ongoing",
                "message_id": str(message.id)
            }
        )

        await interaction.response.send_message(
            embed=embeds.create_success_embed(
                "Voting Started",
                f"Chancellor election voting has begun in {channel.mention}.\n"
                f"**{len(candidates)}** candidates • **{len(voters)}** registered voters"
            ),
            ephemeral=True
        )

    async def conclude_chancellor_election(self, interaction, council_id, channel):
        election_query = self.client.db.list_documents(
            database_id=config.APPWRITE_DB_NAME,
            collection_id=config.COLLECTION_VOTINGS,
            queries=[
                Query.equal("status", "ongoing"),
                Query.equal("type", "chancellor_election"),
                Query.equal("council", council_id),
                Query.order_desc("$updatedAt"),
                Query.limit(1)
            ]
        )
        if election_query["total"] != 1:
            return await interaction.response.send_message(
                embed=embeds.create_error_embed(
                    "No Active Election",
                    "There is no ongoing Chancellor election to conclude."
                ),
                ephemeral=True
            )

        election = election_query["documents"][0]

        winners_query = self.client.db.list_documents(
            database_id=config.APPWRITE_DB_NAME,
            collection_id=config.COLLECTION_REGISTERED,
            queries=[
                Query.equal("election", election["$id"]),
                Query.equal("candidate", True),
                Query.order_desc("votes"),
                Query.limit(1),
            ]
        )
        winners = winners_query["documents"]

        if not winners:
            return await interaction.response.send_message(
                embed=embeds.create_error_embed(
                    "No Results",
                    "Cannot conclude election - no votes were cast."
                ),
                ephemeral=True
            )

        winner = winners[0]

        embed = discord.Embed(
            title="👑 Chancellor Election Results",
            description=f"**The election has concluded!**\n\n"
                       f"The new Chancellor of the Grand Council is:\n\n"
                       f"## {winner['name']}\n\n"
                       f"With **{winner['votes']} vote{'s' if winner['votes'] != 1 else ''}**",
            colour=0x2ECC71,
            timestamp=utils.datetime_now()
        )
        embed.set_footer(text="Congratulations to the new Chancellor! 🎉")

        await channel.send(embed=embed)

        self.client.db.update_document(
            database_id=config.APPWRITE_DB_NAME,
            collection_id=config.COLLECTION_VOTINGS,
            document_id=election['$id'],
            data={"status": "concluded"}
        )

        # Assign Chancellor role
        guild_data = utils.get_guild_data(self.client.db, interaction.guild.id)
        chancellor_role = utils.get_role_by_type(interaction.guild, guild_data, "chancellor")
        winner_member = interaction.guild.get_member(int(winner["discord_id"]))

        if chancellor_role and winner_member:
            # Remove chancellor role from all others
            for member in chancellor_role.members:
                await member.remove_roles(chancellor_role, reason="New Chancellor elected")

            # Add to winner
            await winner_member.add_roles(chancellor_role, reason="Elected as Chancellor")

        await interaction.response.send_message(
            embed=embeds.create_success_embed(
                "Chancellor Election Concluded",
                f"**{winner['name']}** has been elected as Chancellor and assigned the role.\n"
                f"Results have been posted in {channel.mention}."
            ),
            ephemeral=True
        )

async def setup(client: commands.Bot) -> None:
    await client.add_cog(Elections(client))
