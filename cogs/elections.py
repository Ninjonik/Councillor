import datetime

import discord
from appwrite.id import ID
from appwrite.query import Query
from discord import app_commands
from discord.ext import commands

import config
import presets


class Elections(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client

    @app_commands.command(name='elections', description="Handling of Elections")
    @app_commands.choices(action=[
        app_commands.Choice(name="Announce an Election", value="announce"),
        app_commands.Choice(name="Start the Election", value="start"),
        app_commands.Choice(name="Conclude the Election", value="conclude"),
    ])
    @app_commands.describe(
        start="Example: Day.Month.Year Hours:Minutes, (UTC), Example: 24.12.2025 23:56",
        end="Example: Day.Month.Year Hours:Minutes, (UTC), Example: 24.12.2025 23:56",
    )
    async def elections(self, interaction: discord.Interaction, action: app_commands.Choice[str], start: str = None,
                        end: str = None,
                        announcement_channel: discord.TextChannel = None, ping_everyone: bool = False):
        eligible = (await presets.is_eligible(interaction.user, interaction.guild, "president")
                    or await presets.is_eligible(interaction.user, interaction.guild, "vice_president"))

        if not eligible:
            await presets.handle_interaction_error(
                interaction, 
                custom_message="❌ **Not Eligible!** You are not a President or Vice President of this server.",
                ephemeral=True
            )
            return

        if not announcement_channel:
            announcement_channel = interaction.channel

        action = action.value
        council_id = str(interaction.guild.id) + "_c"

        # Handle and convert the datetime
        start_datetime = None
        end_datetime = None

        if start:
            start_datetime = presets.convert_datetime_from_str(start)
        if end:
            end_datetime = presets.convert_datetime_from_str(end)

        # Handle announcing the elections
        if action == "announce":
            # Validate that both start and end dates are provided and valid
            if not start_datetime or not end_datetime:
                await presets.handle_interaction_error(
                    interaction, 
                    custom_message="❌ **Invalid Date Format!** Please use the format: Day.Month.Year Hours:Minutes (e.g., 24.12.2025 23:56)",
                    ephemeral=True
                )
                return
            # Find if there is an already existing election for this council
            check_res = presets.databases.list_documents(
                database_id=config.APPWRITE_DB_NAME,
                collection_id="votings",
                queries=[
                    Query.equal("status", "pending"),
                    Query.equal("council", council_id),
                ]
            )
            if check_res["total"] > 0:
                return await presets.handle_interaction_error(
                    interaction, 
                    custom_message="❌ **Election Already Exists!** There is already a pending election for this server.",
                    ephemeral=True
                )

            embed = discord.Embed(title="📢Elections Announcement!",
                                  description="🎉 Election Alert! 🎉\n\nAttention citizens of "
                                              f"{interaction.guild.name}!\n\nElection day for the Grand Council is "
                                              f"approaching!✨\n\n**Election Time:**\n📅 "
                                              f"From <t:{int(start_datetime.timestamp())}:F> to "
                                              f"<t:{int(end_datetime.timestamp())}:F>"
                                              f"\n\n**Campaign Mode: Activated!**\n🚀 Until "
                                              "election day, you can register to run for Councillor in the Grand "
                                              "Council. But hurry! There's only room for 9 candidates max. "
                                              "🏆\n\n**Voting Reminder:**\n🗳️ **To vote, click the button below and "
                                              "register**. Don't miss out – those who don't vote won't get to shape "
                                              "our future! 🔒\n\n**Eligibility Check:**\n🕵️‍♂️ To register for "
                                              "voting, make sure you've been hanging around our server for the "
                                              "minimum time required by our current laws. 🛡️\n\nDon't sleep on this "
                                              "opportunity! Register now and let your voice be heard in shaping the "
                                              f"future of {interaction.guild.name}! 💬\n\nHappy campaigning, "
                                              "and may the best candidate win! 🏁",
                                  colour=0x00b0f4,
                                  timestamp=presets.datetime_now())

            embed.set_author(name="Democracy Announcement")
            embed.set_image(
                url="https://youth.europa.eu/d8/sites/default/files/styles/1200x600/public/2024-01/voting.png?itok"
                    "=ibzOMTVc")

            embed.set_thumbnail(url="https://www.murfreesborotn.gov/ImageRepository/Document?documentID=14095")
            embed.set_footer(icon_url="https://slate.dan.onl/slate.png")
            message = await announcement_channel.send(content="@everyone" if ping_everyone else None, embed=embed,
                                                      view=presets.ElectionsAnnouncement(self.client))

            councillor_data = await presets.get_councillor_data(interaction.user.id, interaction.guild.id)
            if not councillor_data:
                await presets.handle_interaction_error(
                    interaction, 
                    custom_message="❌ **Councillor Not Found!** Your councillor data could not be found in the database.",
                    ephemeral=True
                )
                return

            presets.databases.create_document(
                database_id=config.APPWRITE_DB_NAME,
                collection_id='votings',
                document_id=str(message.id),
                data={
                    "type": "election",
                    'status': "pending",
                    "voting_end": str(end_datetime),
                    "voting_start": str(start_datetime),
                    "message_id": str(message.id),
                    "title": "Elections Announcement",
                    "council": council_id,
                    "proposer": councillor_data["$id"],
                }
            )
            await interaction.response.send_message("✅ **Success!** Elections have been successfully announced!", ephemeral=True)

        if action == "start":
            election_query = presets.databases.list_documents(
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
                return await presets.handle_interaction_error(
                    interaction, 
                    custom_message="❌ **No Valid Election!** There is no pending election to start.",
                    ephemeral=True
                )

            election = election_query["documents"][0]
            registered_query = presets.databases.list_documents(
                database_id=config.APPWRITE_DB_NAME,
                collection_id="registered",
                queries=[
                    Query.equal("election", election["$id"]),
                ]
            )
            registered = registered_query["documents"]

            voters = []
            candidates = []

            for registeree in registered:
                if registeree["candidate"]:
                    candidates.append(registeree)
                else:
                    voters.append(registeree)

            candidates = candidates[:9]

            embed = discord.Embed(title="🗳️Elections Starting!",
                                  description="🎉 Election Alert! "
                                              f"🎉\n\nAttention citizens of {interaction.guild.name}!\n\n"
                                              "Election day for new councillors of the Grand Council is starting now!"
                                              "✨\nPlease note that you are able to only vote for one councillor."
                                              "\n\n**Election Duration:**\n📅 "
                                              f"From <t:{int(datetime.datetime.fromisoformat(election['voting_start']).timestamp())}:F> to "
                                              f"<t:{int(datetime.datetime.fromisoformat(election['voting_end']).timestamp())}:F>",
                                  colour=0x00b0f4,
                                  timestamp=presets.datetime_now())
            embed.set_author(name="Democracy Announcement")

            for i in range(len(candidates)):
                emoji = presets.generate_keycap_emoji(i + 1)
                embed.add_field(name=f"{emoji} - {candidates[i]['name']}",
                                value="",
                                inline=False)

            embed.set_image(
                url="https://blogs.microsoft.com/wp-content/uploads/prod/sites/5/2023/11/GettyImages-1165687569"
                    "-scaled.jpg")

            view = presets.ElectionsVoting(self.client, candidates)

            for button in view.generate_buttons():
                view.add_item(button)

            message = await announcement_channel.send(content="@everyone" if ping_everyone else None, embed=embed,
                                                      view=view)

            presets.databases.update_document(
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

            await interaction.response.send_message("✅ **Success!** Elections have been successfully started!", ephemeral=True)

        if action == "conclude":
            election_query = presets.databases.list_documents(
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
                return await presets.handle_interaction_error(
                    interaction, 
                    custom_message="❌ **No Valid Election!** There is no ongoing election to conclude.",
                    ephemeral=True
                )

            election = election_query["documents"][0]
            # Target is to have 12 councillors total
            target_count = 12
            # Minimum new councillors is 4
            min_new_councillors = 4

            # Get current councillors to determine how many winners to select
            current_councillors_query = presets.databases.list_documents(
                database_id=config.APPWRITE_DB_NAME,
                collection_id="councillors",
                queries=[
                    Query.equal("council", council_id),
                ]
            )
            current_councillors = current_councillors_query["documents"]
            current_count = len(current_councillors)

            # Calculate how many winners to select
            # If we have fewer than target_count councillors, select enough to reach target_count
            # Otherwise, select at least min_new_councillors
            winners_to_select = max(min_new_councillors, min(9, target_count - current_count))

            winners_query = presets.databases.list_documents(
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

            embed = discord.Embed(title="🙋‍♂️️ Elections Results!",
                                  description="🎉 Election Alert! "
                                              f"🎉\n\nAttention citizens of {interaction.guild.name}!\n\n"
                                              "Election for the new members of the Grand Council has been concluded!"
                                              "✨\nWinners of the election:",
                                  colour=0x00b0f4,
                                  timestamp=presets.datetime_now())
            embed.set_author(name="Democracy Announcement")

            for i in range(len(winners)):
                emoji = presets.generate_keycap_emoji(i + 1)
                embed.add_field(name=f"{emoji} - {winners[i]['name']} - {winners[i]['votes']} votes",
                                value="",
                                inline=False)

            embed.set_image(
                url="https://www.rocklin.ca.us/sites/main/files/imagecache/lightbox/main-images/election_results.png")

            message = await announcement_channel.send(content="@everyone" if ping_everyone else None, embed=embed)

            presets.databases.update_document(
                database_id=config.APPWRITE_DB_NAME,
                collection_id='votings',
                document_id=str(election['$id']),
                data={
                    "status": "concluded",
                    "message_id": str(message.id),
                    "proposer": None,
                    "council": council_id,
                }
            )

            guild_data = presets.get_guild_data(interaction.guild.id)
            councillor_role = interaction.guild.get_role(int(guild_data["councillor_role_id"]))
            chancellor_role = interaction.guild.get_role(int(guild_data["chancellor_role_id"]))

            # Calculate how many councillors to remove
            to_delete = []

            # If we have fewer than (target_count - len(winners)) councillors, we don't remove any
            # If we have more, we remove enough to get to target_count after adding winners
            if current_count <= (target_count - len(winners)):
                # We have fewer councillors than the target, so we don't remove any
                to_delete = []
            else:
                # We need to remove some councillors to maintain the target count
                # Calculate how many to remove
                to_remove_count = current_count + len(winners) - target_count

                # Ensure we're removing at least enough to add min_new_councillors
                if len(winners) < min_new_councillors:
                    # Not enough winners, don't remove any
                    to_delete = []
                elif to_remove_count < min_new_councillors:
                    # Need to remove at least min_new_councillors
                    to_remove_count = min_new_councillors

                # Get the oldest councillors to remove
                if to_remove_count > 0:
                    to_delete_query = presets.databases.list_documents(
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
                presets.databases.delete_document(
                    database_id=config.APPWRITE_DB_NAME,
                    collection_id="councillors",
                    document_id=str(old_councillor["$id"]),
                )
                old_councillor_user = interaction.guild.get_member(int(old_councillor["discord_id"]))
                try:
                    await old_councillor_user.remove_roles(councillor_role, reason="Term ended.")
                except Exception as e:
                    pass
                try:
                    await old_councillor_user.remove_roles(chancellor_role, reason="Term ended.")
                except Exception as e:
                    pass

            # Add new councillors
            for winner in winners:
                presets.databases.create_document(
                    database_id=config.APPWRITE_DB_NAME,
                    collection_id='councillors',
                    document_id=ID.unique(),
                    data={
                        "name": winner["name"],
                        "discord_id": winner["discord_id"],
                        "council": council_id,
                        "proposed": [],
                    }
                )
                winner_user = interaction.guild.get_member(int(winner["discord_id"]))
                try:
                    await winner_user.add_roles(councillor_role, reason="Term started.")
                except Exception as e:
                    print(f"Error adding councillor role to {winner['name']}: {str(e)}")
                    pass

            await interaction.response.send_message("✅ **Success!** Elections have been successfully concluded!", ephemeral=True)


async def setup(client: commands.Bot) -> None:
    await client.add_cog(Elections(client))
