import sys
import traceback

import discord
import discord.utils
from appwrite.query import Query
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.id import ID
from discord.ext import tasks, commands
from colorama import Back, Fore, Style
from datetime import datetime
import datetime
import config
import builtins

client = Client()
client.set_endpoint(config.APPWRITE_ENDPOINT)
client.set_project(config.APPWRITE_PROJECT)
client.set_key(config.APPWRITE_KEY)

databases = Databases(client)


def prefix():
    return (Back.BLACK + Fore.GREEN + datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S") + Back.RESET + Fore.WHITE +
            Style.BRIGHT)


def print(*args, **kwargs):
    """
    Custom print function that adds a prefix to the start of the output.
    """
    message = prefix() + ' ' + ' '.join(map(str, args))
    # Call the original print function from the builtins module
    builtins.print(message, **kwargs)


token = config.BOT_TOKEN


async def ban(member, reason):
    await member.ban(reason=reason)


async def kick(member):
    await member.kick()


def log(content):
    print(prefix() + content)


voting_types = {
    "law": {
        "text": "Law",
        "color": "0x4169E1",
        "emoji": "⚖️",
        "voting_days": 1,
        "required_percentage": 0.5,
    },
    "ultralaw": {
        "text": "Ultra Law",
        "color": "0x8A2BE2",
        "emoji": "🔵",
        "voting_days": 7,
        "required_percentage": 0.8,
},
    "superlaw": {
        "text": "Super Law",
        "color": "0xFF6347",
        "emoji": "📜",
        "voting_days": 1,
        "required_percentage": 0.6,
    },
    "chancellor_election": {
        "text": "Chancellor Election",
        "color": "0x20B2AA",
        "emoji": "🗳️",
        "voting_days": 1,
        "required_percentage": 0.5,
    },
    "chancellor_impeachment": {
        "text": "Chancellor Impeachment",
        "color": "0xFF4500",
        "emoji": "⚠️",
        "voting_days": 1,
        "required_percentage": 0.5,
    },
    "admin_impeachment": {
        "text": "Admin Impeachment",
        "color": "0xFFA500",
        "emoji": "🛑",
        "voting_days": 1,
        "required_percentage": 0.8,
    },
    "admin_election": {
        "text": "Admin Election",
        "color": "0x32CD32",
        "emoji": "👥",
        "voting_days": 1,
        "required_percentage": 0.8,
    },
    "law_suggestion": {
        "text": "Law Suggestion",
        "color": "0x9932CC",
        "emoji": "💡",
        "voting_days": 1,
        "required_percentage": 0,
    },
}


async def createNewVoting(title, description, user, guild, voting_end_date, voting_type, status = "voting"):
    council_id = str(guild.id) + "_c"
    guild_data = await databases.get_document(config.APPWRITE_DB_NAME, "guilds", guild.id)

    voting_type_data = voting_types[voting_type]

    additional_text = ""

    if status == "pending":
        voting_type_data = voting_types["law_suggestion"]
        additional_text = f"- {voting_types[voting_type]['text']}"

    color = discord.Colour(int(voting_type_data["color"], 16))
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_author(name=f"{user.name}#{user.discriminator}",
                     icon_url=user.avatar)
    if not guild_data["voting_channel_id"]:
        return
    channel = guild.get_channel(guild_data["voting_channel_id"])
    embed.set_footer(text=f"⏰ Voting end at: {voting_end_date.strftime('%d.%m.%Y, %H:%M:%S')} UTC+0")
    embed.add_field(name="Type:", value=f"{voting_type_data['emoji']} {voting_type_data['text']} {additional_text}",
                    inline=False)
    message = await channel.send(f"<@&{guild_data['councillor_role_id']}>", embed=embed)
    await message.add_reaction('✅')
    await message.add_reaction('❎')

    databases.create_document(
        database_id=config.APPWRITE_DB_NAME,
        collection_id='votes',
        document_id=ID.unique(),
        data={
            "type": voting_type,
            "voting_end": str(voting_end_date),
            'status': status,
            "suggester": str(user.id),
            "council": council_id,
            "message_id": str(message.id),
            "title": title,
            "description": description,
        }
    )


class CouncilDialog(discord.ui.View):
    def __init__(self, client):
        super().__init__(timeout=None)

    @discord.ui.button(label="Become MP!", style=discord.ButtonStyle.blurple,
                       custom_id="co_council_member", emoji="📋")
    async def councillor(self, interaction: discord.Interaction, button: discord.ui.Button):

        guild_data = databases.get_document(
            database_id=config.APPWRITE_DB_NAME,
            collection_id='guilds',
            document_id=str(interaction.guild.id),
        )
        if not guild_data or not guild_data["councillor_role_id"]:
            await interaction.response.send_message(ephemeral=True, content="❌ Councillor role not set up!")
            return

        member = interaction.user
        councillor_role = interaction.guild.get_role(guild_data["councillor_role_id"])
        if not councillor_role:
            await interaction.response.send_message(ephemeral=True, content="❌ Councillor role not set up!")
            return

        joined_at = member.joined_at
        current_time_utc = datetime.datetime.now(datetime.timezone.utc)
        joined_at_days = (current_time_utc - joined_at).days

        if joined_at_days < config.DAYS_REQUIREMENT:
            await interaction.response.send_message(ephemeral=True, content="❌ Unfortunately you can't become MP yet. "
                                                                            "You have to be in the server for "
                                                                            "at least 3 months.")
            return

        role_id = config.ROLE_REQUIREMENT_ID

        if role_id:
            role = interaction.guild.get_role(role_id)
            if role not in member.roles:
                await interaction.response.send_message(ephemeral=True, content="❌ Unfortunately you can't "
                                                                                "become MP yet. You have obtain "
                                                                                f"the {role.name} role first.")
                return

        councillor_data = databases.list_documents(
            database_id=config.APPWRITE_DB_NAME,
            collection_id='councillors',
            queries=[
                Query.equal('$id', str(interaction.user.id))
            ]
        )

        if not councillor_data["documents"] or len(councillor_data["documents"]) == 0:
            print(f"{prefix()} New raw councillor in {interaction.guild.name} - {interaction.user.name}")

            databases.create_document(
                database_id=config.APPWRITE_DB_NAME,
                collection_id='councillors',
                document_id=f'{str(interaction.user.id)}',
                data={
                    'discord_id': str(interaction.user.id),
                    'name': str(interaction.user.name),
                    'councils': [
                        f"{str(interaction.guild.id)}_c"
                    ]
                }
            )

            await interaction.user.add_roles(councillor_role)
            await interaction.response.send_message(ephemeral=True, content="✅ You have successfully joined this "
                                                                            "server's council! Good luck!")
        else:
            for council in councillor_data["documents"][0]["councils"]:
                if council['$id'] == f"{str(interaction.guild.id)}_c":
                    print(
                        f"{prefix()} Councillor left {interaction.guild.name}'s Council - {interaction.user.name}")
                    updated_councils = [council for council in councillor_data["documents"][0]["councils"]
                                        if council['$id'] != f"{str(interaction.guild.id)}_c"]

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
                        ephemeral=True, content="✅ You have successfully left this server's council.")
                    break
            else:
                print(f"{prefix()} New councillor in {interaction.guild.name} - {interaction.user.name}")

                res = databases.update_document(
                    database_id=config.APPWRITE_DB_NAME,
                    collection_id='councillors',
                    document_id=f'{str(interaction.user.id)}',
                    data={
                        'councils': [
                            *councillor_data["documents"][0]["councils"],
                            f"{str(interaction.guild.id)}_c"
                        ]
                    }
                )

                await interaction.user.add_roles(councillor_role)
                await interaction.response.send_message(ephemeral=True, content="✅ You have successfully joined "
                                                                                "this server's council! Good luck!")

    @discord.ui.button(label="The Grand Council", style=discord.ButtonStyle.danger, custom_id="co_council", emoji="🏛️")
    async def council(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Detailed information in this document: "
                                                "https://docs.google.com/document/d/"
                                                "1f6uNX9h0NX8Ep06N74dVGsMEEqDa0I84YZp-yVvKQsg/edit?usp=sharing")

    async def on_error(self, interaction, error, item):
        print(error)
        print(type(error))
        if isinstance(error, discord.errors.Forbidden):
            await interaction.response.send_message(content="❌ Bot doesn't have the enough permissions for "
                                                            "adding/removing roles. Make sure to move "
                                                            "it's role up in the role's hierarchy in the "
                                                            "discord server's settings.\n"
                                                            "✅ Other actions have been successfully executed.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await interaction.response.send_message(content=f"'{error.param.name}' is a required argument.")
        else:
            print(f'Ignoring exception in CouncilView:', file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
