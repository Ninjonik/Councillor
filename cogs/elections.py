import datetime
import discord
from discord.ext import commands
from discord import app_commands
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
    async def elections(self, interaction: discord.Interaction, action: app_commands.Choice[str], start: str,
                        end: str = None,
                        limit: int = -1, announcement_channel: discord.TextChannel = None, ping_everyone: bool = False):
        eligible = (await presets.is_eligible(interaction.user, interaction.guild, "president")
                    or await presets.is_eligible(interaction.user, interaction.guild, "vice_president"))

        if not eligible:
            await interaction.response.send_message(ephemeral=True,
                                                    content="❌ You are not a Councillor of this server.")
            return

        action = action.value

        # Handle and convert the datetime
        start_datetime = presets.convert_datetime_from_str(start)
        end_datetime = presets.convert_datetime_from_str(end)

        # Handle announcing the elections
        if action == "announce":
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
            await announcement_channel.send(content="@everyone" if ping_everyone else None, embed=embed,
                                            view=presets.ElectionsAnnouncement(self.client))

            await interaction.response.send_message("✅ Elections successfully announced!")


async def setup(client: commands.Bot) -> None:
    await client.add_cog(Elections(client))
