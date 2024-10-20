import sys
import traceback
from typing import Literal

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
    "legislation": {
        "text": "Legislation",
        "color": "0x4169E1",
        "emoji": "⚖️",
        "voting_days": 1,
        "required_percentage": 0.5,
    },
    "amendment": {
        "text": "Amendment",
        "color": "0x8A2BE2",
        "emoji": "🔵",
        "voting_days": 3,
        "required_percentage": 0.66,
    },
    "impeachment": {
        "text": "Impeachment",
        "color": "0xFF6347",
        "emoji": "📜",
        "voting_days": 3,
        "required_percentage": 0.66,
    },
    "other": {
        "text": "Other",
        "color": "0x20B2AA",
        "emoji": "🗳️",
        "voting_days": 3,
        "required_percentage": 0.5,
    },
    "confidence_vote": {
        "text": "Confidence Vote",
        "color": "0xFF4500",
        "emoji": "⚠️",
        "voting_days": 3,
        "required_percentage": 0.66,
    },
    "decree": {
        "text": "Decree",
        "color": "0xFFA500",
        "emoji": "🛑",
        "voting_days": 1,
        "required_percentage": 0.5,
    },
}

ROLE = Literal["councillor", "chancellor", "judiciary", "president", "vice_president"]


def datetime_now():
    return datetime.datetime.now(datetime.UTC)


def convert_datetime_from_str(datetime_str: None | str) -> None | datetime.datetime:
    formats = ["%d.%m.%Y %H:%M", "%d-%m-%Y %H:%M", "%d/%m/%Y %H:%M"]
    for fmt in formats:
        try:
            datetime_obj = datetime.datetime.strptime(datetime_str, fmt)
            datetime_obj.replace(tzinfo=datetime.timezone.utc)
            return datetime_obj
        except ValueError:
            pass
    else:
        return None


async def is_eligible(user: discord.Member, guild: discord.Guild, role: ROLE) -> bool:
    guild_data = databases.get_document(
        database_id=config.APPWRITE_DB_NAME,
        collection_id='guilds',
        document_id=str(guild.id),
    )

    if not guild_data or not guild_data[f"{role}_role_id"]:
        print("❌ Higher roles don't exist in this server or there is no voting channel set. Guild: ", guild.id)
        return False

    role_id = guild_data[f"{role}_role_id"]
    role = guild.get_role(int(role_id))
    if role in user.roles:
        return True

    return False


async def create_new_voting(bot_client: discord.Client, title, description, user, guild: discord.Guild, voting_type,
                            status="voting", voting_end_date=None):
    council_id = str(guild.id) + "_c"
    guild_data = await get_guild_data(guild.id)

    voting_type_data = voting_types[voting_type]

    additional_text = ""

    if not voting_end_date:
        current_date = datetime_now()
        if current_date.hour >= 12:
            next_day = current_date + datetime.timedelta(days=voting_type_data["voting_days"] + 1)
        else:
            next_day = current_date + datetime.timedelta(days=voting_type_data["voting_days"])

        # Set the time to midnight UTC
        voting_end_date = datetime.datetime(next_day.year, next_day.month, next_day.day, 0, 0, 1)

    color = discord.Colour(int(voting_type_data["color"], 16))
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_author(name=f"{user.name}#{user.discriminator}",
                     icon_url=user.avatar)
    if not guild_data["voting_channel_id"]:
        return

    channel = guild.get_channel(int(guild_data["voting_channel_id"]))
    embed.set_footer(text=f"⏰ Voting end at: {voting_end_date.strftime('%d.%m.%Y, %H:%M:%S')} UTC+0")
    embed.add_field(name="Type:", value=f"{voting_type_data['emoji']} {voting_type_data['text']} {additional_text}",
                    inline=False)
    message = await channel.send(f"<@&{guild_data['councillor_role_id']}>", embed=embed, view=VotingDialog(bot_client))

    new_voting = databases.create_document(
        database_id=config.APPWRITE_DB_NAME,
        collection_id='votings',
        document_id=str(message.id),
        data={
            "type": voting_type,
            'status': status,
            "voting_end": str(voting_end_date),
            "message_id": str(message.id),
            "title": title,
            "description": description,
            "council": council_id,
            "proposer": str(user.id),
        }
    )

    embed.set_footer(text=f"⏰ Voting end at: {voting_end_date.strftime('%d.%m.%Y, %H:%M:%S')} UTC+0 | "
                          f"ID: {new_voting['$id']}")
    await message.edit(embed=embed)


async def get_guild_data(guild_id: int | str):
    return databases.get_document(
        database_id=config.APPWRITE_DB_NAME,
        collection_id="guilds",
        document_id=str(guild_id)
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
        councillor_role = interaction.guild.get_role(int(guild_data["councillor_role_id"]))
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


class VotingDialog(discord.ui.View):
    def __init__(self, client):
        super().__init__(timeout=None)

    async def send_dm(self, member, message):
        try:
            dm_channel = await member.create_dm()
            await dm_channel.send(message)
        except Exception as e:
            print(f"Failed to send DM to {member.name}: {str(e)}")

    async def handle_vote(self, interaction, stance: bool):
        member = interaction.user
        guild = interaction.guild
        message = interaction.message

        if member.bot:
            return await interaction.response.send_message(
                "❌ Unfortunately for you my dear robot friend,"
                " you can't vote.", ephemeral=True)

        try:
            # Fetch voting data
            voting_data = databases.list_documents(
                database_id=config.APPWRITE_DB_NAME,
                collection_id='votings',
                queries=[Query.equal('message_id', str(message.id))]
            )

            if not voting_data or not voting_data.get("documents") or not voting_data["documents"]:
                return await interaction.response.send_message("❌ Voting couldn't be found. "
                                                               "Please contact an administrator "
                                                               "if you feel like this is a bug.",
                                                               ephemeral=True)

            voting_data = voting_data["documents"][0]

            # Check eligibility
            eligible = await is_eligible(member, guild, "councillor")
            if not eligible:
                return await interaction.response.send_message("❌ You're not a councillor in this server.",
                                                               ephemeral=True)

            # Convert voting end date to UTC
            voting_end_date_str = voting_data['voting_end']
            voting_end_date = datetime.datetime.fromisoformat(voting_end_date_str)

            # Compare current time with voting end time (UTC)
            current_time_utc = datetime_now()
            if current_time_utc > voting_end_date:
                return await interaction.response.send_message("❌ You can't vote past the voting date.",
                                                               ephemeral=True)

            # Check if vote already exists for this user for this voting
            existing_vote = databases.list_documents(
                database_id=config.APPWRITE_DB_NAME,
                collection_id='votes',
                queries=[
                    Query.equal('voting', voting_data["$id"]),
                    Query.equal('councillor', str(member.id))
                ]
            )

            if existing_vote and existing_vote["documents"] and existing_vote["documents"][0]:
                databases.delete_document(
                    database_id=config.APPWRITE_DB_NAME,
                    collection_id="votes",
                    document_id=existing_vote["documents"][0]["$id"]
                )
                print(f"Removing previous vote from the db for {member.name} in {guild.name}")

            # Create new vote
            databases.create_document(
                database_id=config.APPWRITE_DB_NAME,
                collection_id='votes',
                document_id=ID.unique(),
                data={
                    "councillor": str(member.id),
                    "voting": voting_data["$id"],
                    "stance": stance
                }
            )

            await interaction.response.send_message(
                f"- Your vote ({"✅" if stance else "❌"}) has been successfully casted!", ephemeral=True)
            print(f"New vote added: {stance} by {member.name} on {voting_data['$id']}")

        except Exception as e:
            # Log the error
            print(f"An error occurred while handling the vote: {str(e)}")
            await interaction.response.send_message(
                f"❌ An unexpected error occurred while processing your vote. Please try again later.",
                ephemeral=True)

    @discord.ui.button(style=discord.ButtonStyle.success,
                       custom_id="vd_yes", emoji="✅")
    async def vd_yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        return await self.handle_vote(interaction, True)

    @discord.ui.button(style=discord.ButtonStyle.danger,
                       custom_id="vd_no", emoji="❎")
    async def vd_no(self, interaction: discord.Interaction, button: discord.ui.Button):
        return await self.handle_vote(interaction, False)

    @discord.ui.button(style=discord.ButtonStyle.secondary,
                       custom_id="vd_veto", emoji="⛔")
    async def vd_veto(self, interaction: discord.Interaction, button: discord.ui.Button):
        eligible = await is_eligible(interaction.user, interaction.guild, "councillor")
        if not eligible:
            return await interaction.response.send_message("❌ You are not a President, Vice-President or a "
                                                           "Chancellor to veto this vote.", ephemeral=True)
        await interaction.response.send_modal(VetoReason())

    async def on_error(self, interaction, error, item):
        if isinstance(error, commands.MissingRequiredArgument):
            await interaction.response.send_message(content=f"'{error.param.name}' is a required argument.")
        else:
            print(f'Ignoring exception in VotingDialog:', file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)


class VetoReason(discord.ui.Modal, title='Veto'):
    reason = discord.ui.TextInput(label='Reason for the veto')

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason.value
        try:
            updated_voting = databases.get_document(
                database_id=config.APPWRITE_DB_NAME,
                collection_id="votings",
                document_id=str(interaction.message.id),

            )
            print(updated_voting)

            guild_data = await get_guild_data(interaction.guild.id)

            channel = interaction.guild.get_channel(int(guild_data["voting_channel_id"]))
            embed = discord.Embed(title=f"❌ {updated_voting['title']} vetoed!", color=0xFF0000)
            embed.add_field(name="Vetoed by:", value=interaction.user.name, inline=False)
            embed.add_field(name="Reason:", value=reason, inline=False)
            if updated_voting['proposer']:
                embed.set_footer(text=f"Vote originally proposed by: {updated_voting['proposer']['name']}")
            await channel.send(embed=embed)
            await interaction.response.send_message("✅ Legislation successfully vetoed.", ephemeral=True)
        except Exception as e:
            print(e)
            print(traceback.format_exc())
            await interaction.response.send_message("❌ Legislation with this ID does not exist.", ephemeral=True)
            return

    async def on_error(self, interaction: discord.Interaction, error):
        await interaction.response.send_message('There was an error while processing the request.', ephemeral=True)


class ElectionsAnnouncement(discord.ui.View):
    def __init__(self, client):
        super().__init__(timeout=None)

    @discord.ui.button(style=discord.ButtonStyle.success,
                       custom_id="ea_register", emoji="🗳️", label="Register to vote")
    async def ea_register(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(style=discord.ButtonStyle.danger,
                       custom_id="ea_candidate", emoji="🚀", label="Candidate")
    async def ea_candidate(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    async def on_error(self, interaction, error, item):
        if isinstance(error, commands.MissingRequiredArgument):
            await interaction.response.send_message(content=f"'{error.param.name}' is a required argument.")
        else:
            print(f'Ignoring exception in ElectionsAnnouncement:', file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
