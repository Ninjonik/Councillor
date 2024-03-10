from asyncio import tasks
from time import sleep

import discord
import discord.utils
from appwrite.query import Query
from discord.ext import tasks, commands
from discord import app_commands
from colorama import Back, Fore, Style
from datetime import datetime
import platform
import os
import random
import asyncio
import json
import datetime
import string
from pprint import pprint
import config
from PIL import Image, ImageDraw, ImageFont
import time
from googleapiclient import discovery

from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.id import ID

client = Client()
client.set_endpoint(config.APPWRITE_ENDPOINT)
client.set_project(config.APPWRITE_PROJECT)
client.set_key(config.APPWRITE_KEY)

databases = Databases(client)

def prefix():
    return (Back.BLACK + Fore.GREEN + datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S") + Back.RESET + Fore.WHITE +
            Style.BRIGHT)


token = config.BOT_TOKEN


async def ban(member, reason):
    await member.ban(reason=reason)


async def kick(member):
    await member.kick()


def log(content):
    print(prefix() + content)


async def _add_player(player_id, rating_percentage, current_time):
    try:
        pass
        # cursor.execute(
        #     "INSERT INTO players (discord_id, rating, created_at, updated_at) VALUES (%s, %s, %s, %s) "
        #     "ON DUPLICATE KEY UPDATE rating = %s, updated_at = %s",
        #     (player_id, rating_percentage, current_time, current_time, rating_percentage, current_time))
        # connection.commit()
    except Exception as e:
        # connection.rollback()
        raise e


class CouncilDialog(discord.ui.View):
    def __init__(self, client):
        super().__init__(timeout=None)

    @discord.ui.button(label="Become MP!", style=discord.ButtonStyle.blurple,
                       custom_id="co_council_member", emoji="📋")
    async def councillor(self, interaction: discord.Interaction, button: discord.ui.Button):

        member = interaction.user
        councillor_role = interaction.guild.get_role(config.ROLE_COUNCILLOR_ID)
        print("a")
        if not councillor_role:
            await interaction.response.send_message(ephemeral=True, content="❌ Councillor role not set up!")
            return

        joined_at = member.joined_at
        current_time_utc = datetime.datetime.now(datetime.timezone.utc)
        joined_at_days = (current_time_utc - joined_at).days
        print("b")

        if joined_at_days < 180:
            await interaction.response.send_message(ephemeral=True, content="❌ Unfortunately you can't become MP yet. "
                                                    "You have to be in the server for at least 6 months.")
            return

        role_id = config.ROLE_REQUIREMENT_ID
        print("c")

        if role_id:
            role = interaction.guild.get_role(role_id)
            if role not in member.roles:
                await interaction.response.send_message(ephemeral=True, content="❌ Unfortunately you can't "
                                                                                "become MP yet. "
                                                        f"You have obtain the {role.name} role first.")
                return
        print("d")

        councillor_data = databases.list_documents(
            database_id=config.APPWRITE_DB_NAME,
            collection_id='councillors',
            queries=[
                Query.equal('$id', str(interaction.user.id))
            ]
        )

        print(prefix(), councillor_data.documents, councillor_data.documents.length, sep=", ")

        if councillor_data.documents.length == 0:
            print(f"{prefix()} New raw councillor in {interaction.guild.name} - {interaction.user.name}")

            res = databases.create_document(
                database_id=config.APPWRITE_DB_NAME,
                collection_id='councillors',
                document_id=f'{str(interaction.user.id)}',
                data={
                    'discord_id': str(interaction.guild.id),
                    'name': str(interaction.guild.name),
                    'councils': [
                        f"{str(interaction.guild.id)}_c"
                    ]
                }
            )

            await interaction.user.add_roles(councillor_role)
            await interaction.response.send_message(ephemeral=True, content="✔️ You have successfully joined this "
                                                                            "server's council! Good luck!")
        else:
            for council in councillor_data.documents[0].councils:
                if council['$id'] == interaction.guild.id:
                    print(f"{prefix()} New councillor in {interaction.guild.name} - {interaction.user.name}")

                    res = databases.update_document(
                        database_id=config.APPWRITE_DB_NAME,
                        collection_id='councillors',
                        document_id=f'{str(interaction.user.id)}',
                        data={
                            'councils': [
                                *councillor_data.documents[0].councils,
                                f"{str(interaction.guild.id)}_c"
                            ]
                        }
                    )

                    await interaction.user.add_roles(councillor_role)
                    await interaction.response.send_message(ephemeral=True, content="✔️ You have successfully joined "
                                                                                    "this server's council! Good luck!")
                    break
            else:
                print(
                    f"{prefix()} Councillor left {interaction.guild.name}'s Council - {interaction.user.name}")
                updated_councils = [council for council in councillor_data.documents[0].councils if
                                    council['$id'] != interaction.guild.id]

                print(f"{prefix()} Updated councils: {updated_councils}")

                res = databases.update_document(
                    database_id=config.APPWRITE_DB_NAME,
                    collection_id='councillors',
                    document_id=f'{str(interaction.user.id)}',
                    data={
                        'councils': updated_councils
                    }
                )

                await interaction.user.remove_roles(councillor_role)
                await interaction.response.send_message(
                    ephemeral=True, content="✔️ You have successfully left this server's council.")

    @discord.ui.button(label="The Grand Council", style=discord.ButtonStyle.danger, custom_id="co_council", emoji="🏛️")
    async def council(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Detailed information in this document: "
                                                "https://docs.google.com/document/d/"
                                                "1f6uNX9h0NX8Ep06N74dVGsMEEqDa0I84YZp-yVvKQsg/edit?usp=sharing")
