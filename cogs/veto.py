import discord
from appwrite.query import Query
from discord.ext import commands
from discord import app_commands
from typing import List

import datetime

import config
import presets
from presets import databases
from appwrite.id import ID


class Veto(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client

    @app_commands.command(name='veto', description="An emergency power that can be used to veto any law being currently "
                                                   "voted on.")
    async def veto(self, interaction: discord.Interaction, law_id: str, reason: str):
        guild_data = presets.databases.get_document(
            database_id=config.APPWRITE_DB_NAME,
            collection_id='guilds',
            document_id=str(interaction.guild.id),
        )
        if not guild_data or not guild_data["voting_channel_id"] or not guild_data["chancellor_role_id"] \
                or not guild_data["president_role_id"] or not guild_data["vice_president_role_id"]:
            print("❌ Higher roles don't exist in this server or there is no voting channel set.")
            await interaction.response.send_message("❌ Higher roles don't exist in this server.")
            return

        is_eligible = False
        for role_id in [guild_data["chancellor_role_id"], guild_data["president_role_id"],
                        guild_data["vice_president_role_id"]]:
            role = interaction.guild.get_role(int(role_id))
            if role in interaction.user.roles:
                is_eligible = True
                break

        if not is_eligible:
            await interaction.response.send_message("❌ You are not President/Vice-President"
                                                    "/Chancellor to veto the law.")
            return

        try:
            presets.databases.update_document(
                database_id=config.APPWRITE_DB_NAME,
                collection_id="votes",
                document_id=law_id,
                data={
                    "status": "vetoed",
                }
            )

            updated_vote = presets.databases.get_document(
                database_id=config.APPWRITE_DB_NAME,
                collection_id="votes",
                document_id=law_id,
            )

            channel = interaction.guild.get_channel(int(guild_data["voting_channel_id"]))
            embed = discord.Embed(title=f"❌ {updated_vote['title']} vetoed!", color=0xFF0000)
            embed.add_field(name="Vetoed by:", value=interaction.user.name, inline=False)
            embed.add_field(name="Reason:", value=reason, inline=False)
            embed.set_footer(text=f"Vote originally proposed by: {updated_vote['suggester']['name']}")
            await channel.send(embed=embed)
            await interaction.response.send_message("✅ Law successfully vetoed.")
        except Exception as e:
            await interaction.response.send_message("❌ Law with this ID does not exist.")
            return


async def setup(client: commands.Bot) -> None:
    await client.add_cog(Veto(client))
