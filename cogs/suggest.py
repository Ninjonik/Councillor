import discord
from appwrite.query import Query
from discord.ext import commands
from discord import app_commands
import datetime

import config
import presets
from presets import databases
from appwrite.id import ID


class Suggest(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client

    @app_commands.command(name='suggest', description="Creates a Council Suggestion for MPs to vote!")
    @app_commands.choices(choices=[
        app_commands.Choice(name="Law", value="law"),
        app_commands.Choice(name="Superlaw", value="superlaw"),
        app_commands.Choice(name="Ultralaw", value="ultralaw"),
    ])
    async def assembly_suggest(self, interaction: discord.Interaction, title: str, description: str,
                               type: app_commands.Choice[str]):

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
        next_day = current_date + datetime.timedelta(days=1)
        voting_end_date = datetime.datetime(next_day.year, next_day.month, next_day.day, 0, 0, 1)

        if councillor['suggestions']:
            for suggestion in councillor['suggestions']:
                if suggestion['council']['$id'] == council_id:
                    db_voting_end = datetime.datetime.fromisoformat(suggestion['voting_end']).date()
                    current_date = datetime.datetime.utcnow().date()

                    tomorrow_date = current_date + datetime.timedelta(days=1)

                    if db_voting_end == tomorrow_date:
                        await interaction.response.send_message(ephemeral=True,
                                                                content="❌ You can't post another voting "
                                                                        "suggestion today.")
                        return

        await presets.createNewVoting(title, description, interaction.user, interaction.guild, voting_end_date,
                                      type, "pending")
        await interaction.response.send_message("✅ Suggestion successfully created!")


async def setup(client: commands.Bot) -> None:
    await client.add_cog(Suggest(client))
