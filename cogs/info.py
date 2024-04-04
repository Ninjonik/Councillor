import config

import discord
import discord.utils
from discord.ext import commands
from discord import app_commands

from presets import databases


class Information(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client

    @app_commands.command(name="info", description="Who is in our current council?")
    async def assembly_info(self, interaction: discord.Interaction):

        council = databases.get_document(
            database_id=config.APPWRITE_DB_NAME,
            collection_id='councils',
            document_id=str(interaction.guild.id) + "_c",
        )
        council_members = []
        chancellor = "None"
        for councillor in council['councillors']:
            councillor_discord = interaction.guild.get_member(int(councillor['$id'])).mention
            if council['chancellor'] and councillor['$id'] == council['chancellor']:
                chancellor = councillor_discord
            council_members.append(councillor_discord)

        embed = discord.Embed(
            title=f"**Council**",
            description="**The Grand Council** is a group of members (MPs) who have the right to vote on proposed "
                        "changes to the "
                        f"{interaction.guild.name} server. These changes are put forward by the Chancellor, "
                        "who is also responsible for guiding the direction of the Grand Council and the server. MPs "
                        "also have the ability to propose new laws to the Chancellor for future consideration.",
            colour=discord.Colour.green()
        )
        embed.set_thumbnail(url=interaction.guild.icon)
        embed.add_field(
            name="**Current Chancellor**",
            value=chancellor,
            inline=True,
        )
        if len(council_members) > 1:
            embed.add_field(
                name="Current Council Members",
                value=", ".join(council_members),
                inline=True,
            )

        await interaction.response.send_message(embed=embed)


async def setup(client: commands.Bot) -> None:
    await client.add_cog(Information(client))
