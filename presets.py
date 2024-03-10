from asyncio import tasks
from time import sleep

import discord
import discord.utils
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


class AssemblyDialog(discord.ui.View):
    def __init__(self, client):
        super().__init__(timeout=None)

    @discord.ui.button(label="Become MP!", style=discord.ButtonStyle.blurple,
                       custom_id="co_council_member", emoji="📋")
    async def assembly_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        # self.cursor.execute("SELECT discord_id FROM assemblies WHERE discord_id='%s'" % interaction.user.id)
        # assembly = self.cursor.fetchall()
        assembly = []
        current_time = datetime.datetime.now()
        if not assembly:
            print(f"{prefix()} User was not in DB - {interaction.user.name}")
            # self.cursor.execute("INSERT INTO assemblies (discord_id, created_at, updated_at) "
            #                     "VALUES (%s, '%s', '%s')"
            #                     % (interaction.user.id, current_time, current_time))
            # self.connection.commit()
            await interaction.user.add_roles(
                discord.utils.get(interaction.user.guild.roles, name="Assembly Member"))
        else:
            print(f"{prefix()} Removing User from Assembly - {interaction.user.name}")
            # self.cursor.execute("DELETE FROM assembly_suggestions WHERE author_discord_id=%s"
            #                     % interaction.user.id)
            # self.cursor.execute("DELETE FROM assemblies WHERE discord_id=%s"
            #                     % interaction.user.id)
            # self.connection.commit()
            await interaction.user.remove_roles(
                discord.utils.get(interaction.user.guild.roles, name="Assembly Member"))
        await interaction.response.send_message("Your roles have been updated.", ephemeral=True)

    @discord.ui.button(label="The Grand Council", style=discord.ButtonStyle.danger, custom_id="co_council", emoji="🏛️")
    async def assembly(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Detailed information in this document: "
                                                "https://docs.google.com/document/d/"
                                                "1f6uNX9h0NX8Ep06N74dVGsMEEqDa0I84YZp-yVvKQsg/edit?usp=sharing")
