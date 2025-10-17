from typing import Literal, Optional
from datetime import datetime, timezone
import discord
from appwrite.query import Query
import config

ROLE = Literal["councillor", "chancellor", "judiciary", "president", "vice_president"]
voting_types = {
    "legislation": {
        "text": "Legislation",
        "color": 0x4169E1,
        "emoji": "⚖️",
        "voting_days": 1,
        "required_percentage": 0.5,
    },
    "amendment": {
        "text": "Amendment",
        "color": 0x8A2BE2,
        "emoji": "🔵",
        "voting_days": 3,
        "required_percentage": 0.66,
    },
    "impeachment": {
        "text": "Impeachment",
        "color": 0xFF6347,
        "emoji": "📜",
        "voting_days": 3,
        "required_percentage": 0.66,
    },
    "other": {
        "text": "Other",
        "color": 0x20B2AA,
        "emoji": "🗳️",
        "voting_days": 3,
        "required_percentage": 0.5,
    },
    "confidence_vote": {
        "text": "Confidence Vote",
        "color": 0xFF4500,
        "emoji": "⚠️",
        "voting_days": 3,
        "required_percentage": 0.66,
    },
    "decree": {
        "text": "Decree",
        "color": 0xFFA500,
        "emoji": "🛑",
        "voting_days": 1,
        "required_percentage": 0.5,
    },
}


def datetime_now():
    return datetime.now(timezone.utc)


def convert_datetime_from_str(datetime_str: Optional[str]) -> Optional[datetime]:
    if not datetime_str:
        return None

    formats = ["%d.%m.%Y %H:%M", "%d-%m-%Y %H:%M", "%d/%m/%Y %H:%M"]
    for fmt in formats:
        try:
            dt = datetime.strptime(datetime_str, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def generate_keycap_emoji(number: int) -> str:
    keycap_emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣']
    return keycap_emojis[number - 1] if 1 <= number <= 9 else '🔢'


def get_guild_data(databases, guild_id: any):
    try:
        return databases.get_document(
            database_id=config.APPWRITE_DB_NAME,
            collection_id="guilds",
            document_id=str(guild_id)
        )
    except Exception:
        return None


async def get_councillor_data(databases, discord_id: int, guild_id: int):
    try:
        result = databases.list_documents(
            database_id=config.APPWRITE_DB_NAME,
            collection_id='councillors',
            queries=[
                Query.equal("discord_id", str(discord_id)),
                Query.equal("council", str(guild_id) + "_c"),
            ]
        )
        return result["documents"][0] if result["documents"] else None
    except Exception:
        return None


async def is_eligible(databases, user: discord.Member, guild: discord.Guild, role: ROLE) -> bool:
    guild_data = get_guild_data(databases, guild.id)

    if not guild_data or not guild_data.get(f"{role}_role_id"):
        return False

    role_obj = guild.get_role(int(guild_data[f"{role}_role_id"]))
    return role_obj in user.roles if role_obj else False


async def handle_interaction_error(
    interaction: discord.Interaction,
    error: Optional[Exception] = None,
    custom_message: Optional[str] = None,
    ephemeral: bool = True
) -> None:
    message = custom_message or "❌ An unexpected error occurred. Please try again later."

    if error and not custom_message:
        if isinstance(error, discord.errors.Forbidden):
            message = "❌ Missing Permissions! The bot doesn't have the required permissions."
        elif isinstance(error, discord.errors.NotFound):
            message = "❌ Not Found! The requested resource could not be found."
        elif isinstance(error, discord.errors.HTTPException):
            message = f"❌ Discord API Error! {error.status}: {error.text}"
        else:
            import sys, traceback
            print(f"Error in interaction: {error}")
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(message, ephemeral=ephemeral)
        else:
            await interaction.followup.send(message, ephemeral=ephemeral)
    except Exception as e:
        print(f"Failed to send error message: {e}")
