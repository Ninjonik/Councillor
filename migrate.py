"""
Database migration script - creates Appwrite collections
Run this once to set up your database structure
"""

from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.permission import Permission
from appwrite.role import Role
from appwrite.exception import AppwriteException
import config
from logger import log

client = Client()
client.set_endpoint(config.APPWRITE_ENDPOINT)
client.set_project(config.APPWRITE_PROJECT_ID)
client.set_key(config.APPWRITE_API_KEY)

db = Databases(client)

def purge_collections():
    """Delete all existing collections and their data"""
    collection_ids = [
        config.COLLECTION_COUNCILLORS,
        config.COLLECTION_VOTINGS,
        config.COLLECTION_REGISTERED,
        config.COLLECTION_VOTED,
        config.COLLECTION_PROPOSALS,
        config.COLLECTION_GUILDS,
        # Old collections for backwards compatibility
        "members",
        "elections",
        "votes"
    ]

    for collection_id in collection_ids:
        try:
            db.delete_collection(
                database_id=config.APPWRITE_DATABASE_ID,
                collection_id=collection_id
            )
            log.success(f"Deleted collection: {collection_id}")
        except AppwriteException as e:
            if "not found" in str(e).lower() or "404" in str(e):
                log.info(f"Collection not found (skipping): {collection_id}")
            else:
                log.warning(f"Error deleting collection {collection_id}: {e}")

def create_collections():
    """Create necessary collections"""

    collections = [
        {
            "id": config.COLLECTION_COUNCILLORS,
            "name": "Councillors",
            "attributes": [
                {"key": "name", "type": "string", "size": 255, "required": True},
                {"key": "discord_id", "type": "string", "size": 255, "required": True},
                {"key": "council", "type": "string", "size": 255, "required": True},
            ]
        },
        {
            "id": config.COLLECTION_VOTINGS,
            "name": "Votings",
            "attributes": [
                {"key": "type", "type": "string", "size": 50, "required": True},  # "election" or "proposal"
                {"key": "status", "type": "string", "size": 50, "required": True},  # "pending", "ongoing", "concluded"
                {"key": "voting_start", "type": "datetime", "required": True},
                {"key": "voting_end", "type": "datetime", "required": True},
                {"key": "message_id", "type": "string", "size": 255, "required": False},
                {"key": "title", "type": "string", "size": 500, "required": True},
                {"key": "council", "type": "string", "size": 255, "required": True},
                {"key": "proposer", "type": "string", "size": 255, "required": False},  # Reference to councillor ID
            ]
        },
        {
            "id": config.COLLECTION_REGISTERED,
            "name": "Registered",
            "attributes": [
                {"key": "election", "type": "string", "size": 255, "required": True},  # Reference to voting ID
                {"key": "discord_id", "type": "string", "size": 255, "required": True},
                {"key": "name", "type": "string", "size": 255, "required": True},
                {"key": "candidate", "type": "boolean", "required": True},  # True if running, False if just voting
                {"key": "votes", "type": "integer", "required": False, "default": 0},
            ]
        },
        {
            "id": config.COLLECTION_VOTED,
            "name": "Voted",
            "attributes": [
                {"key": "voting_id", "type": "string", "size": 255, "required": True},
                {"key": "voter_id", "type": "string", "size": 255, "required": True},
                {"key": "candidates", "type": "string", "size": 1000, "required": True},  # JSON array of candidate IDs
            ]
        },
        {
            "id": config.COLLECTION_PROPOSALS,
            "name": "Proposals",
            "attributes": [
                {"key": "title", "type": "string", "size": 255, "required": True},
                {"key": "description", "type": "string", "size": 10000, "required": True},
                {"key": "author_id", "type": "string", "size": 255, "required": True},
                {"key": "author_name", "type": "string", "size": 255, "required": True},
                {"key": "status", "type": "string", "size": 50, "required": True},
                {"key": "votes_for", "type": "integer", "required": False, "default": 0},
                {"key": "votes_against", "type": "integer", "required": False, "default": 0},
                {"key": "created_at", "type": "datetime", "required": True}
            ]
        },
        {
            "id": config.COLLECTION_GUILDS,
            "name": "Guilds",
            "attributes": [
                {"key": "guild_id", "type": "string", "size": 255, "required": True},
                {"key": "councillor_role_id", "type": "string", "size": 255, "required": False},
                {"key": "chancellor_role_id", "type": "string", "size": 255, "required": False},
                {"key": "president_role_id", "type": "string", "size": 255, "required": False},
                {"key": "vice_president_role_id", "type": "string", "size": 255, "required": False},
            ]
        }
    ]

    for collection_data in collections:
        try:
            # Try to create collection
            collection = db.create_collection(
                database_id=config.APPWRITE_DATABASE_ID,
                collection_id=collection_data["id"],
                name=collection_data["name"],
                permissions=[
                    Permission.read(Role.any()),
                    Permission.create(Role.any()),
                    Permission.update(Role.any()),
                    Permission.delete(Role.any())
                ]
            )
            log.success(f"Created collection: {collection_data['name']}")

            # Create attributes
            for attr in collection_data["attributes"]:
                try:
                    attr_copy = attr.copy()
                    attr_type = attr_copy.pop("type")
                    if attr_type == "string":
                        db.create_string_attribute(
                            config.APPWRITE_DATABASE_ID,
                            collection_data["id"],
                            **attr_copy
                        )
                    elif attr_type == "integer":
                        db.create_integer_attribute(
                            config.APPWRITE_DATABASE_ID,
                            collection_data["id"],
                            **attr_copy
                        )
                    elif attr_type == "boolean":
                        db.create_boolean_attribute(
                            config.APPWRITE_DATABASE_ID,
                            collection_data["id"],
                            **attr_copy
                        )
                    elif attr_type == "datetime":
                        db.create_datetime_attribute(
                            config.APPWRITE_DATABASE_ID,
                            collection_data["id"],
                            **attr_copy
                        )
                    log.success(f"  Created attribute: {attr_copy['key']}")
                except AppwriteException as e:
                    if "already exists" in str(e).lower():
                        log.warning(f"  Attribute exists: {attr_copy['key']}")
                    else:
                        log.error(f"  Error creating attribute {attr_copy['key']}: {e}")

        except AppwriteException as e:
            if "already exists" in str(e).lower():
                log.warning(f"Collection exists: {collection_data['name']}")
            else:
                log.error(f"Error creating collection {collection_data['name']}: {e}")

if __name__ == "__main__":
    log.info("=" * 60)
    log.info("DATABASE MIGRATION SCRIPT")
    log.info("=" * 60)
    log.warning("⚠️  WARNING: This will DELETE ALL existing data!")
    log.warning("⚠️  All collections will be purged and recreated.")
    log.info("=" * 60)

    confirmation = input("\nType 'YES' to confirm and proceed with migration: ")

    if confirmation.strip() != "YES":
        log.info("Migration cancelled.")
        exit(0)

    log.info("\n" + "=" * 60)
    log.info("Starting database migration...")
    log.info("=" * 60 + "\n")

    log.info("Step 1: Purging existing collections...")
    purge_collections()

    log.info("\nStep 2: Creating new collections...")
    create_collections()

    log.success("\n" + "=" * 60)
    log.success("✅ Migration complete!")
    log.success("=" * 60)
