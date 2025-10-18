import discord
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.query import Query
from appwrite.id import ID
from appwrite.exception import AppwriteException
import config
from datetime import datetime
from typing import Optional, Dict
from logger import log

# Appwrite client setup
client = Client()
client.set_endpoint(config.APPWRITE_ENDPOINT)
client.set_project(config.APPWRITE_PROJECT_ID)
client.set_key(config.APPWRITE_API_KEY)
db = Databases(client)

def datetime_now():
    """Get current UTC datetime"""
    return datetime.utcnow()

def convert_datetime_from_str(date_str: str) -> Optional[datetime]:
    """Convert date string DD.MM.YYYY HH:MM to datetime object"""
    try:
        return datetime.strptime(date_str, "%d.%m.%Y %H:%M")
    except (ValueError, AttributeError):
        return None

def generate_keycap_emoji(number: int) -> str:
    """Generate keycap emoji for numbers 1-9"""
    keycaps = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
    return keycaps[number - 1] if 1 <= number <= 9 else str(number)

# Guild data helpers
def get_guild_data(db_client, guild_id: int) -> Optional[Dict]:
    """Get guild configuration from Appwrite"""
    try:
        result = db_client.list_documents(
            database_id=config.APPWRITE_DATABASE_ID,
            collection_id=config.COLLECTION_GUILDS,
            queries=[Query.equal("guild_id", str(guild_id))]
        )
        return result['documents'][0] if result['total'] > 0 else None
    except AppwriteException:
        return None

def create_guild_data(db_client, guild_id: int):
    """Create guild configuration"""
    try:
        return db_client.create_document(
            database_id=config.APPWRITE_DATABASE_ID,
            collection_id=config.COLLECTION_GUILDS,
            document_id=ID.unique(),
            data={"guild_id": str(guild_id)}
        )
    except AppwriteException as e:
        log.error(f"Error creating guild data: {e}")
        return None

def get_role_by_type(guild: discord.Guild, guild_data: Optional[Dict], role_type: str) -> Optional[discord.Role]:
    """Get Discord role object by type from guild config"""
    if not guild_data:
        return None

    role_key = f"{role_type}_role_id"
    role_id = guild_data.get(role_key)

    if role_id:
        return guild.get_role(int(role_id))
    return None

# Universal role checker - checks Discord role first, then checks Appwrite
async def has_role(member: discord.Member, role_type: str, db_client=None) -> bool:
    """
    Check if member has a specific role type.
    First checks Discord roles, then checks Appwrite database.

    Args:
        member: Discord member to check
        role_type: Type of role (president, vice_president, chancellor, councillor, citizen)
        db_client: Database client (optional, defaults to global db)

    Returns:
        bool: True if member has the role
    """
    if db_client is None:
        db_client = db

    # Get guild configuration
    guild_data = get_guild_data(db_client, member.guild.id)

    # Check Discord role first
    role = get_role_by_type(member.guild, guild_data, role_type)
    if role and role in member.roles:
        return True

    # Fallback: Check Appwrite database
    if role_type == "councillor":
        councillor_data = await get_councillor_data(db_client, member.id, member.guild.id)
        return councillor_data is not None
    elif role_type == "chancellor":
        # Check if user is stored as chancellor in database
        try:
            council_id = str(member.guild.id) + "_c"
            result = db_client.list_documents(
                database_id=config.APPWRITE_DATABASE_ID,
                collection_id=config.COLLECTION_COUNCILLORS,
                queries=[
                    Query.equal("discord_id", str(member.id)),
                    Query.equal("council", council_id),
                    Query.equal("is_chancellor", True)
                ]
            )
            return result['total'] > 0
        except AppwriteException:
            return False

    return False

# Convenience functions for role checking
def is_president(member: discord.Member, guild_data: Optional[Dict] = None) -> bool:
    """Check if member has president role (synchronous Discord-only check)"""
    if guild_data is None:
        guild_data = get_guild_data(db, member.guild.id)
    role = get_role_by_type(member.guild, guild_data, "president")
    return role is not None and role in member.roles

def is_vice_president(member: discord.Member, guild_data: Optional[Dict] = None) -> bool:
    """Check if member has vice president role (synchronous Discord-only check)"""
    if guild_data is None:
        guild_data = get_guild_data(db, member.guild.id)
    role = get_role_by_type(member.guild, guild_data, "vice_president")
    return role is not None and role in member.roles

def is_chancellor(member: discord.Member, guild_data: Optional[Dict] = None) -> bool:
    """Check if member has chancellor role (synchronous Discord-only check)"""
    if guild_data is None:
        guild_data = get_guild_data(db, member.guild.id)
    role = get_role_by_type(member.guild, guild_data, "chancellor")
    return role is not None and role in member.roles

def is_councillor(member: discord.Member, guild_data: Optional[Dict] = None) -> bool:
    """Check if member has councillor role (synchronous Discord-only check)"""
    if guild_data is None:
        guild_data = get_guild_data(db, member.guild.id)
    role = get_role_by_type(member.guild, guild_data, "councillor")
    return role is not None and role in member.roles

def is_citizen(member: discord.Member, guild_data: Optional[Dict] = None) -> bool:
    """Check if member has citizen role (synchronous Discord-only check)"""
    if guild_data is None:
        guild_data = get_guild_data(db, member.guild.id)
    role = get_role_by_type(member.guild, guild_data, "citizen")
    return role is not None and role in member.roles

async def is_eligible(db_client, user: discord.Member, guild: discord.Guild, role: str) -> bool:
    """
    Check if user is eligible for a role (checks both Discord roles and Appwrite).
    This is the main function to use for authorization checks.
    """
    return await has_role(user, role, db_client)

# Councillor helpers
async def get_councillor_data(db_client, user_id: int, guild_id: int):
    """Get councillor data for a user"""
    try:
        council_id = str(guild_id) + "_c"
        result = db_client.list_documents(
            database_id=config.APPWRITE_DATABASE_ID,
            collection_id=config.COLLECTION_COUNCILLORS,
            queries=[
                Query.equal("discord_id", str(user_id)),
                Query.equal("council", council_id)
            ]
        )
        return result['documents'][0] if result['total'] > 0 else None
    except AppwriteException:
        return None

async def get_all_councillors(db_client, guild_id: int):
    """Get all councillors for a guild"""
    try:
        council_id = str(guild_id) + "_c"
        result = db_client.list_documents(
            database_id=config.APPWRITE_DATABASE_ID,
            collection_id=config.COLLECTION_COUNCILLORS,
            queries=[Query.equal("council", council_id)]
        )
        return result['documents']
    except AppwriteException:
        return []

# Election helpers
def is_member_old_enough(member: discord.Member) -> bool:
    """Check if member has been in server for at least VOTING_AGE_DAYS"""
    if not member.joined_at:
        return False
    days_in_server = (datetime_now() - member.joined_at.replace(tzinfo=None)).days
    return days_in_server >= config.VOTING_AGE_DAYS

async def check_already_registered(db_client, election_id: str, user_id: str) -> bool:
    """Check if user is already registered for an election"""
    try:
        result = db_client.list_documents(
            database_id=config.APPWRITE_DATABASE_ID,
            collection_id=config.COLLECTION_REGISTERED,
            queries=[
                Query.equal("election", election_id),
                Query.equal("discord_id", user_id)
            ]
        )
        return result['total'] > 0
    except AppwriteException:
        return False

async def register_for_election(db_client, election_id: str, user_id: str, username: str, as_candidate: bool):
    """Register user for election (as voter or candidate)"""
    try:
        return db_client.create_document(
            database_id=config.APPWRITE_DATABASE_ID,
            collection_id=config.COLLECTION_REGISTERED,
            document_id=ID.unique(),
            data={
                "election": election_id,
                "discord_id": user_id,
                "name": username,
                "candidate": as_candidate,
                "votes": 0
            }
        )
    except AppwriteException as e:
        log.error(f"Error registering for election: {e}")
        return None

async def has_voted(db_client, voting_id: str, voter_id: str) -> bool:
    """Check if user has already voted"""
    try:
        result = db_client.list_documents(
            database_id=config.APPWRITE_DATABASE_ID,
            collection_id=config.COLLECTION_VOTED,
            queries=[
                Query.equal("voting_id", voting_id),
                Query.equal("voter_id", voter_id)
            ]
        )
        return result['total'] > 0
    except AppwriteException:
        return False

async def record_vote(db_client, voting_id: str, voter_id: str, candidate_ids: list):
    """Record a vote"""
    try:
        import json
        return db_client.create_document(
            database_id=config.APPWRITE_DATABASE_ID,
            collection_id=config.COLLECTION_VOTED,
            document_id=ID.unique(),
            data={
                "voting_id": voting_id,
                "voter_id": voter_id,
                "candidates": json.dumps(candidate_ids)
            }
        )
    except AppwriteException as e:
        log.error(f"Error recording vote: {e}")
        return None

# Proposal helpers
async def get_active_proposals(db_client, guild_id: int):
    """Get active proposals"""
    try:
        result = db_client.list_documents(
            database_id=config.APPWRITE_DATABASE_ID,
            collection_id=config.COLLECTION_PROPOSALS,
            queries=[Query.equal("status", "active")]
        )
        return result['documents']
    except AppwriteException:
        return []

async def create_proposal(db_client, title: str, description: str, author_id: str, author_name: str):
    """Create new proposal"""
    try:
        return db_client.create_document(
            database_id=config.APPWRITE_DATABASE_ID,
            collection_id=config.COLLECTION_PROPOSALS,
            document_id=ID.unique(),
            data={
                "title": title,
                "description": description,
                "author_id": author_id,
                "author_name": author_name,
                "status": "active",
                "votes_for": 0,
                "votes_against": 0,
                "created_at": datetime_now().isoformat()
            }
        )
    except AppwriteException as e:
        log.error(f"Error creating proposal: {e}")
        return None

# Role syncing
async def sync_roles(member: discord.Member, role_type: str):
    """
    Sync Discord roles with database role.

    Args:
        member: Discord member to sync roles for
        role_type: Type of role to assign (president, vice_president, chancellor, councillor, citizen)
    """
    guild = member.guild
    guild_data = get_guild_data(db, guild.id)

    if not guild_data:
        log.error(f"Cannot sync roles - guild {guild.id} not configured")
        return

    # Get role objects
    chancellor_role = get_role_by_type(guild, guild_data, "chancellor")
    councillor_role = get_role_by_type(guild, guild_data, "councillor")
    citizen_role = get_role_by_type(guild, guild_data, "citizen")

    # Remove all gov roles first (except President/VP which are permanent)
    roles_to_remove = [r for r in [chancellor_role, councillor_role, citizen_role] if r and r in member.roles]
    if roles_to_remove:
        await member.remove_roles(*roles_to_remove)

    # Add new role
    role_to_add = get_role_by_type(guild, guild_data, role_type)
    if role_to_add:
        await member.add_roles(role_to_add)

# Ministry helpers
async def get_ministry(db_client, ministry_id: str):
    """Get ministry by ID"""
    try:
        return db_client.get_document(
            database_id=config.APPWRITE_DATABASE_ID,
            collection_id=config.COLLECTION_MINISTRIES,
            document_id=ministry_id
        )
    except AppwriteException:
        return None

async def get_all_ministries(db_client, guild_id: int):
    """Get all ministries for a guild"""
    try:
        result = db_client.list_documents(
            database_id=config.APPWRITE_DATABASE_ID,
            collection_id=config.COLLECTION_MINISTRIES,
            queries=[Query.equal("guild_id", str(guild_id))]
        )
        return result['documents']
    except AppwriteException:
        return []

async def create_ministry(db_client, guild_id: int, name: str, role_id: str = None, deputy_role_id: str = None):
    """Create a new ministry"""
    try:
        return db_client.create_document(
            database_id=config.APPWRITE_DATABASE_ID,
            collection_id=config.COLLECTION_MINISTRIES,
            document_id=ID.unique(),
            data={
                "guild_id": str(guild_id),
                "name": name,
                "role_id": role_id or "",
                "deputy_role_id": deputy_role_id or "",
                "minister_id": "",
                "deputy_minister_id": ""
            }
        )
    except AppwriteException as e:
        log.error(f"Error creating ministry: {e}")
        return None

async def update_ministry(db_client, ministry_id: str, data: dict):
    """Update ministry data"""
    try:
        return db_client.update_document(
            database_id=config.APPWRITE_DATABASE_ID,
            collection_id=config.COLLECTION_MINISTRIES,
            document_id=ministry_id,
            data=data
        )
    except AppwriteException as e:
        log.error(f"Error updating ministry: {e}")
        return None

async def delete_ministry(db_client, ministry_id: str):
    """Delete a ministry"""
    try:
        db_client.delete_document(
            database_id=config.APPWRITE_DATABASE_ID,
            collection_id=config.COLLECTION_MINISTRIES,
            document_id=ministry_id
        )
        return True
    except AppwriteException as e:
        log.error(f"Error deleting ministry: {e}")
        return False

# Voting helpers
async def record_vote_on_proposal(db_client, voting_id: str, voter_id: str, stance: bool):
    """Record a vote on a proposal (True = for, False = against)"""
    try:
        return db_client.create_document(
            database_id=config.APPWRITE_DATABASE_ID,
            collection_id=config.COLLECTION_VOTES,
            document_id=ID.unique(),
            data={
                "voting": voting_id,
                "voter_id": voter_id,
                "stance": stance
            }
        )
    except AppwriteException as e:
        log.error(f"Error recording vote: {e}")
        return None

async def has_voted_on_proposal(db_client, voting_id: str, voter_id: str) -> bool:
    """Check if user has voted on a proposal"""
    try:
        result = db_client.list_documents(
            database_id=config.APPWRITE_DATABASE_ID,
            collection_id=config.COLLECTION_VOTES,
            queries=[
                Query.equal("voting", voting_id),
                Query.equal("voter_id", voter_id)
            ]
        )
        return result['total'] > 0
    except AppwriteException:
        return False

async def handle_interaction_error(interaction: discord.Interaction, error: Exception, custom_message: str = None):
    """Handle interaction errors gracefully"""
    from embeds import create_error_embed

    error_message = custom_message or f"An error occurred: {str(error)}"
    log.error(f"Interaction error: {error}")

    try:
        if interaction.response.is_done():
            await interaction.followup.send(
                embed=create_error_embed("Error", error_message),
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                embed=create_error_embed("Error", error_message),
                ephemeral=True
            )
    except:
        pass
