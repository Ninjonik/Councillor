import discord
from appwrite.query import Query
from discord.ext import commands
from discord import app_commands
import datetime

import config
from presets import databases
from appwrite.id import ID


class Suggest(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client

    @app_commands.command(name='suggest', description="Creates a Council Suggestion for MPs to vote!")
    async def assembly_suggest(self, interaction: discord.Interaction, title: str, description: str):

        councillor = databases.get_document(
            database_id=config.APPWRITE_DB_NAME,
            collection_id='councillors',
            document_id=str(interaction.user.id)
        )

        council_id = str(interaction.guild.id) + "_c"

        if councillor['councils']:
            for council in councillor['councils']:
                if council['$id'] == council_id: break
            else:
                await interaction.response.send_message(ephemeral=True, content="❌ You are not a MP of this server.")
                return
        else:
            await interaction.response.send_message(ephemeral=True, content="❌ You are not a MP of this server.")
            return

        current_date = datetime.datetime.utcnow()
        voting_end_date = datetime.datetime(current_date.year, current_date.month, current_date.day + 1, 0, 0, 0)

        if councillor['suggestions']:
            for suggestion in councillor['suggestions']:
                if suggestion['council']['$id'] == council_id:
                    db_voting_end = datetime.datetime.fromisoformat(suggestion['voting_end']).date()
                    current_date = datetime.datetime.utcnow().date()
                    if (db_voting_end.year == current_date.year and db_voting_end.month == current_date.month
                            and db_voting_end.day == current_date.day + 1):
                        await interaction.response.send_message(ephemeral=True, content="❌ You can't post another "
                                                                                        "voting suggestion today.")
                        return

        embed = discord.Embed(title=title, description=description, color=0xb3ffb3)
        embed.set_author(name=f"{interaction.user.name}#{interaction.user.discriminator}",
                         icon_url=interaction.user.avatar)
        channel = interaction.guild.get_channel(1217791295754604596)
        message = await channel.send(embed=embed)
        await message.add_reaction('✅')
        await message.add_reaction('❎')

        print(voting_end_date)

        databases.create_document(
            database_id=config.APPWRITE_DB_NAME,
            collection_id='votes',
            document_id=ID.unique(),
            data={
                "type": "law_suggestion",
                "voting_end": str(voting_end_date),
                'status': 'pending',
                "suggester": str(interaction.user.id),
                "council": council_id
            }
        )
        await interaction.response.send_message("✅ Suggestion successfully created!")


async def setup(client: commands.Bot) -> None:
    await client.add_cog(Suggest(client))
