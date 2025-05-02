import config

import discord
import discord.utils
from discord.ext import commands
from discord import app_commands

import presets
from presets import databases


class Information(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client

    @app_commands.command(name="info", description="Who is in our current council?")
    async def assembly_info(self, interaction: discord.Interaction):
        try:
            guild_data = databases.get_document(
                database_id=config.APPWRITE_DB_NAME,
                collection_id='guilds',
                document_id=str(interaction.guild.id),
            )

            if not guild_data:
                await presets.handle_interaction_error(
                    interaction, 
                    custom_message="❌ **Guild Not Found!** The data for this server could not be found."
                )
                return

            council_id = str(interaction.guild.id) + "_c"

            # Get councillors from the councillors collection
            councillors_query = databases.list_documents(
                database_id=config.APPWRITE_DB_NAME,
                collection_id="councillors",
                queries=[
                    presets.Query.equal("council", council_id),
                ]
            )

            councillors = councillors_query["documents"]

            council_members = []
            chancellor = "None"

            # Check if chancellor role is set
            if guild_data.get("chancellor_role_id"):
                chancellor_role = interaction.guild.get_role(int(guild_data["chancellor_role_id"]))
                if chancellor_role:
                    for member in interaction.guild.members:
                        if chancellor_role in member.roles:
                            chancellor = member.mention
                            break

            # Add all councillors to the list
            for councillor in councillors:
                member = interaction.guild.get_member(int(councillor['discord_id']))
                if not member:
                    # Skip members who have left the server
                    continue

                council_members.append(member.mention)

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
        except Exception as e:
            await presets.handle_interaction_error(
                interaction, 
                e, 
                "❌ **Error!** There was an error while fetching council information."
            )


async def setup(client: commands.Bot) -> None:
    await client.add_cog(Information(client))
