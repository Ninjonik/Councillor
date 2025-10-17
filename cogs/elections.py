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

class Elections(commands.Cog):
    """Election management for Council seats"""

    def __init__(self, client: commands.Bot):
        self.client = client

    @app_commands.command(name='elections', description="[President/VP] Manage Council elections")
    @app_commands.choices(action=[
        app_commands.Choice(name="📢 Announce Election", value="announce"),
        app_commands.Choice(name="🗳️ Start Voting", value="start"),
        app_commands.Choice(name="🏆 Conclude & Count Votes", value="conclude"),
    ])
    @app_commands.describe(
        start="Format: DD.MM.YYYY HH:MM (UTC) - Example: 24.12.2025 23:56",
        end="Format: DD.MM.YYYY HH:MM (UTC) - Example: 31.12.2025 23:56",
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
        eligible = (
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
            collection_id="votings",
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

        message = await channel.send(
            content="@everyone" if ping_everyone else None,
            embed=embed,
            view=views.ElectionsAnnouncement(self.client.db)
        )

        councillor_data = await utils.get_councillor_data(self.client.db, interaction.user.id, interaction.guild.id)
        if not councillor_data:
            return await interaction.response.send_message(
                embed=embeds.create_error_embed(
                    "Error",
                    "Your councillor data could not be found. You may need to be a councillor to announce elections."
                ),
                ephemeral=True
            )

        self.client.db.create_document(
            database_id=config.APPWRITE_DB_NAME,
            collection_id='votings',
            document_id=str(message.id),
            data={
                "type": "election",
                "status": "pending",
                "voting_end": end_datetime.isoformat(),
                "voting_start": start_datetime.isoformat(),
                "message_id": str(message.id),
                "title": "Council Elections",
                "council": council_id,
                "proposer": councillor_data["$id"],
            }
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
            collection_id="votings",
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
            collection_id="registered",
            queries=[Query.equal("election", election["$id"])]
        )
        registered = registered_query["documents"]

        candidates = [r for r in registered if r["candidate"]][:9]
        voters = [r for r in registered if not r["candidate"]]

        if not candidates:
            return await interaction.response.send_message(
                embed=embeds.create_error_embed(
                    "No Candidates",
                    "Cannot start election with no candidates. Please wait for candidates to register."
                ),
                ephemeral=True
            )

        embed = discord.Embed(
            title="🗳️ Council Elections - Voting Now Open",
            description=f"**Welcome, citizens of {interaction.guild.name}!**\n\n"
                        f"The voting period has begun for new Grand Council members. "
                        f"Please review the candidates below and cast your vote.\n\n"
                        f"**{len(candidates)} candidate{'s' if len(candidates) != 1 else ''}** • "
                        f"**{len(voters)} registered voter{'s' if len(voters) != 1 else ''}**\n\n"
                        f"⏰ **Voting Period**\n"
                        f"From <t:{int(datetime.fromisoformat(election['voting_start']).timestamp())}:F>\n"
                        f"To <t:{int(datetime.fromisoformat(election['voting_end']).timestamp())}:F>",
            colour=0x3498DB,
            timestamp=utils.datetime_now()
        )

        for i, candidate in enumerate(candidates):
            emoji = utils.generate_keycap_emoji(i + 1)
            embed.add_field(
                name=f"{emoji} {candidate['name']}",
                value="Running for Council seat",
                inline=True
            )

        embed.set_footer(text="Click a button below to cast your vote • One vote per person")

        view = views.ElectionsVoting(self.client.db, candidates)
        for button in view.generate_buttons():
            view.add_item(button)

        message = await channel.send(
            content="@everyone" if ping_everyone else None,
            embed=embed,
            view=view
        )

        self.client.db.update_document(
            database_id=config.APPWRITE_DB_NAME,
            collection_id='votings',
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
            collection_id="votings",
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
        target_count = 12
        min_new_councillors = 4

        current_councillors_query = self.client.db.list_documents(
            database_id=config.APPWRITE_DB_NAME,
            collection_id="councillors",
            queries=[Query.equal("council", council_id)]
        )
        current_count = len(current_councillors_query["documents"])

        winners_to_select = max(min_new_councillors, min(9, target_count - current_count))

        winners_query = self.client.db.list_documents(
            database_id=config.APPWRITE_DB_NAME,
            collection_id="registered",
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

        embed = discord.Embed(
            title="🏆 Election Results",
            description=f"**Attention, citizens of {interaction.guild.name}!**\n\n"
                        f"The election has concluded. Here are your newly elected Grand Council members:",
            colour=0x2ECC71,
            timestamp=utils.datetime_now()
        )

        for i, winner in enumerate(winners):
            emoji = utils.generate_keycap_emoji(i + 1)
            vote_text = f"{winner['votes']} vote{'s' if winner['votes'] != 1 else ''}"
            embed.add_field(
                name=f"{emoji} {winner['name']}",
                value=f"✅ Elected with {vote_text}",
                inline=False
            )

        embed.set_footer(text="Congratulations to the winners! 🎉")

        await channel.send(content="@everyone" if ping_everyone else None, embed=embed)

        self.client.db.update_document(
            database_id=config.APPWRITE_DB_NAME,
            collection_id='votings',
            document_id=str(election['$id']),
            data={"status": "concluded", "council": council_id}
        )

        guild_data = utils.get_guild_data(self.client.db, interaction.guild.id)
        councillor_role = interaction.guild.get_role(int(guild_data["councillor_role_id"])) if guild_data and guild_data.get("councillor_role_id") else None
        chancellor_role = interaction.guild.get_role(int(guild_data["chancellor_role_id"])) if guild_data and guild_data.get("chancellor_role_id") else None

        if current_count > (target_count - len(winners)):
            to_remove_count = min(current_count + len(winners) - target_count, current_count)
            if to_remove_count > 0:
                to_delete_query = self.client.db.list_documents(
                    database_id=config.APPWRITE_DB_NAME,
                    collection_id="councillors",
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
                            collection_id="councillors",
                            document_id=str(old_councillor["$id"])
                        )
                        old_member = interaction.guild.get_member(int(old_councillor["discord_id"]))
                        if old_member and councillor_role:
                            await old_member.remove_roles(councillor_role, reason="Term ended")
                            if chancellor_role and chancellor_role in old_member.roles:
                                await old_member.remove_roles(chancellor_role, reason="Term ended")
                    except Exception as e:
                        print(f"Error removing councillor: {e}")

        added_count = 0
        for winner in winners:
            try:
                self.client.db.create_document(
                    database_id=config.APPWRITE_DB_NAME,
                    collection_id='councillors',
                    document_id=ID.unique(),
                    data={
                        "name": winner["name"],
                        "discord_id": winner["discord_id"],
                        "council": council_id,
                    }
                )
                winner_member = interaction.guild.get_member(int(winner["discord_id"]))
                if winner_member and councillor_role:
                    await winner_member.add_roles(councillor_role, reason="Elected to Council")
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

async def setup(client: commands.Bot) -> None:
    await client.add_cog(Elections(client))

