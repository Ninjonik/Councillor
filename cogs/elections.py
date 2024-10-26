import datetime
import discord
from appwrite.query import Query
from discord.ext import commands
from discord import app_commands

import config
import presets


class Elections(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client

    @app_commands.command(name='elections', description="Handling of Elections")
    @app_commands.choices(action=[
        app_commands.Choice(name="Announce an Election", value="announce"),
        app_commands.Choice(name="Start an Election", value="start"),
        app_commands.Choice(name="Announce Election Results", value="results"),
    ])
    @app_commands.describe(
        start="Example: Day.Month.Year Hours:Minutes, (UTC), Example: 24.12.2025 23:56",
        end="Example: Day.Month.Year Hours:Minutes, (UTC), Example: 24.12.2025 23:56",
    )
    async def elections(self, interaction: discord.Interaction, action: app_commands.Choice[str], start: str = None,
                        end: str = None,
                        limit: int = -1, announcement_channel: discord.TextChannel = None, ping_everyone: bool = False):
        eligible = (await presets.is_eligible(interaction.user, interaction.guild, "president")
                    or await presets.is_eligible(interaction.user, interaction.guild, "vice_president"))

        if not eligible:
            await interaction.response.send_message(ephemeral=True,
                                                    content="❌ You are not a Councillor of this server.")
            return

        if not announcement_channel:
            announcement_channel = interaction.channel

        action = action.value
        council_id = str(interaction.guild.id) + "_c"

        # Handle and convert the datetime
        if start:
            start_datetime = presets.convert_datetime_from_str(start)
        if end:
            end_datetime = presets.convert_datetime_from_str(end)

        # Handle announcing the elections
        if action == "announce":
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
                return await interaction.response.send_message(ephemeral=True,
                                                               content="❌ There is already an election that is pending.")

            limit = limit if limit != -1 else 4
            embed = discord.Embed(title="📢Elections Announcement!",
                                  description="🎉 Election Alert! 🎉\n\nAttention citizens of "
                                              f"{interaction.guild.name}!\n\nElection day for {limit} councillors of"
                                              f" the Grand Council is "
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
                    "proposer": str(interaction.user.id),
                }
            )
            await interaction.response.send_message("✅ Elections successfully announced!", ephemeral=True)

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
                return await interaction.response.send_message(ephemeral=True,
                                                               content="❌ There is no valid election to start.")

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
                                              "🎉\n\nAttention citizens of {interaction.guild.name}!\n\n"
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

            await interaction.response.send_message("✅ Elections successfully started!", ephemeral=True)


async def setup(client: commands.Bot) -> None:
    await client.add_cog(Elections(client))
