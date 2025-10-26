#!/usr/bin/env python3
"""
Database migration script - creates Appwrite collections
Run this once to set up your database structure
"""

from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.permission import Permission
from appwrite.role import Role
from appwrite.exception import AppwriteException
from colorama import Fore, Style, init
import sys

try:
    import config
except ImportError:
    config = None  # satisfy linters; we exit immediately below
    print(f"{Fore.RED}✗ Error: 'config' module not found. Please create a config.py file with APPWRITE_ENDPOINT, APPWRITE_PROJECT, APPWRITE_KEY, and APPWRITE_DB_NAME.{Style.RESET_ALL}")
    sys.exit(1)

# Initialize colorama
init(autoreset=True)

# Simple logger using colorama
class Logger:
    @staticmethod
    def success(msg):
        print(f"{Fore.GREEN}✓ {msg}{Style.RESET_ALL}")

    @staticmethod
    def info(msg):
        print(f"{Fore.CYAN}ℹ {msg}{Style.RESET_ALL}")

    @staticmethod
    def warning(msg):
        print(f"{Fore.YELLOW}⚠ {msg}{Style.RESET_ALL}")

    @staticmethod
    def error(msg):
        print(f"{Fore.RED}✗ {msg}{Style.RESET_ALL}")

log = Logger()

# Initialize Appwrite client
client = Client()
client.set_endpoint(config.APPWRITE_ENDPOINT)
client.set_project(config.APPWRITE_PROJECT)
client.set_key(config.APPWRITE_KEY)

db = Databases(client)

def find_database_by_name(database_name):
    """Find database by name and return its ID"""
    try:
        dbs = db.list()
        for database in dbs['databases']:
            if database['name'] == database_name:
                return database['$id']
        return None
    except AppwriteException as e:
        log.error(f"Failed to list databases: {str(e)}")
        return None

def create_or_get_database():
    """Create database or get existing one"""
    db_id = find_database_by_name(config.APPWRITE_DB_NAME)
    if db_id:
        log.info(f"Using existing database: {config.APPWRITE_DB_NAME} (ID: {db_id})")
        return db_id

    try:
        database = db.create(
            database_id=config.APPWRITE_DB_NAME.lower().replace(" ", "_"),
            name=config.APPWRITE_DB_NAME
        )
        db_id = database['$id']
        log.success(f"Created database: {config.APPWRITE_DB_NAME} (ID: {db_id})")
        return db_id
    except AppwriteException as e:
        log.error(f"Failed to create database: {str(e)}")
        return None

def purge_collections(database_id):
    """Delete all existing collections and their data"""
    collection_ids = [
        "guilds", "councils", "councillors", "ministries", "votings",
        "votes", "election_candidates", "registered_voters", "settings", "logs"
    ]

    for collection_id in collection_ids:
        try:
            db.delete_collection(database_id=database_id, collection_id=collection_id)
            log.success(f"Deleted collection: {collection_id}")
        except AppwriteException as e:
            msg = str(e).lower()
            if "not found" in msg or "could not be found" in msg or "404" in msg:
                log.info(f"Collection not found (skipping): {collection_id}")
            else:
                log.warning(f"Error deleting collection {collection_id}: {str(e)}")

def create_collections(database_id):
    """Create necessary collections"""
    collections = [
        {
            "id": "guilds",
            "name": "Guilds",
            "attributes": [
                {"key": "guild_id", "type": "string", "size": 36, "required": True},
                {"key": "name", "type": "string", "size": 256, "required": True},
                {"key": "description", "type": "string", "size": 1024, "required": False},
                # Defaults cannot be set on required attributes in Appwrite
                {"key": "enabled", "type": "boolean", "required": False, "default": True},
                {"key": "logging_enabled", "type": "boolean", "required": False, "default": True},
                {"key": "voting_channel_id", "type": "string", "size": 36, "required": False},
                {"key": "announcement_channel_id", "type": "string", "size": 36, "required": False},
                {"key": "councillor_role_id", "type": "string", "size": 36, "required": False},
                {"key": "chancellor_role_id", "type": "string", "size": 36, "required": False},
                {"key": "minister_role_id", "type": "string", "size": 36, "required": False},
                {"key": "president_role_id", "type": "string", "size": 36, "required": False},
                {"key": "vice_president_role_id", "type": "string", "size": 36, "required": False},
                {"key": "judiciary_role_id", "type": "string", "size": 36, "required": False},
                {"key": "citizen_role_id", "type": "string", "size": 36, "required": False},
                {"key": "days_requirement", "type": "integer", "required": False, "default": 180},
                {"key": "max_councillors", "type": "integer", "required": False, "default": 9},
            ]
        },
        {
            "id": "councils",
            "name": "Councils",
            "attributes": [
                {"key": "council_id", "type": "string", "size": 50, "required": True},
                {"key": "guild_id", "type": "string", "size": 36, "required": True},
                {"key": "current_chancellor_id", "type": "string", "size": 36, "required": False},
                {"key": "election_in_progress", "type": "boolean", "required": False, "default": False},
            ]
        },
        {
            "id": "councillors",
            "name": "Councillors",
            "attributes": [
                {"key": "discord_id", "type": "string", "size": 36, "required": True},
                {"key": "name", "type": "string", "size": 256, "required": True},
                {"key": "council_id", "type": "string", "size": 50, "required": True},
                {"key": "joined_at", "type": "datetime", "required": True},
                {"key": "active", "type": "boolean", "required": False, "default": True},
                {"key": "is_chancellor", "type": "boolean", "required": False, "default": False},
                {"key": "ministry_ids", "type": "string", "size": 100, "required": False, "array": True},
            ]
        },
        {
            "id": "ministries",
            "name": "Ministries",
            "attributes": [
                {"key": "name", "type": "string", "size": 256, "required": True},
                {"key": "description", "type": "string", "size": 1024, "required": False},
                {"key": "council_id", "type": "string", "size": 50, "required": True},
                {"key": "minister_discord_id", "type": "string", "size": 36, "required": False},
                {"key": "role_ids", "type": "string", "size": 100, "required": False, "array": True},
                {"key": "created_by", "type": "string", "size": 36, "required": False},
                {"key": "created_at", "type": "datetime", "required": True},
                {"key": "active", "type": "boolean", "required": False, "default": True},
            ]
        },
        {
            "id": "votings",
            "name": "Votings",
            "attributes": [
                {"key": "type", "type": "enum", "elements": ['legislation', 'amendment', 'impeachment', 'confidence_vote', 'decree', 'other', 'election', 'chancellor_election'], "required": True},
                {"key": "status", "type": "enum", "elements": ['pending', 'voting', 'passed', 'failed', 'cancelled'], "required": True},
                {"key": "title", "type": "string", "size": 512, "required": True},
                {"key": "description", "type": "string", "size": 4096, "required": False},
                {"key": "council_id", "type": "string", "size": 50, "required": True},
                {"key": "proposer_id", "type": "string", "size": 36, "required": False},
                {"key": "message_id", "type": "string", "size": 36, "required": False},
                {"key": "voting_start", "type": "datetime", "required": False},
                {"key": "voting_end", "type": "datetime", "required": True},
                {"key": "required_percentage", "type": "float", "required": False, "default": 0.5},
                {"key": "result_announced", "type": "boolean", "required": False, "default": False},
            ]
        },
        {
            "id": "votes",
            "name": "Votes",
            "attributes": [
                {"key": "voting_id", "type": "string", "size": 36, "required": True},
                {"key": "councillor_id", "type": "string", "size": 36, "required": False},
                {"key": "discord_id", "type": "string", "size": 36, "required": True},
                {"key": "stance", "type": "boolean", "required": True},
                {"key": "candidate_id", "type": "string", "size": 36, "required": False},
                {"key": "voted_at", "type": "datetime", "required": True},
            ]
        },
        {
            "id": "election_candidates",
            "name": "Election Candidates",
            "attributes": [
                {"key": "voting_id", "type": "string", "size": 36, "required": True},
                {"key": "discord_id", "type": "string", "size": 36, "required": True},
                {"key": "name", "type": "string", "size": 256, "required": True},
                {"key": "registered_at", "type": "datetime", "required": True},
                {"key": "vote_count", "type": "integer", "required": False, "default": 0},
                {"key": "elected", "type": "boolean", "required": False, "default": False},
            ]
        },
        {
            "id": "registered_voters",
            "name": "Registered Voters",
            "attributes": [
                {"key": "voting_id", "type": "string", "size": 36, "required": True},
                {"key": "discord_id", "type": "string", "size": 36, "required": True},
                {"key": "name", "type": "string", "size": 256, "required": True},
                {"key": "registered_at", "type": "datetime", "required": True},
                {"key": "has_voted", "type": "boolean", "required": False, "default": False},
            ]
        },
        {
            "id": "settings",
            "name": "Settings",
            "attributes": [
                {"key": "key", "type": "string", "size": 256, "required": True},
                {"key": "value", "type": "string", "size": 4096, "required": True},
                {"key": "type", "type": "enum", "elements": ['string', 'integer', 'boolean', 'json', 'array'], "required": True},
                {"key": "description", "type": "string", "size": 512, "required": False},
                {"key": "guild_id", "type": "string", "size": 36, "required": False},
                {"key": "editable_by", "type": "enum", "elements": ['admin', 'chancellor', 'president'], "required": False, "default": 'admin'},
            ]
        },
        {
            "id": "logs",
            "name": "Logs",
            "attributes": [
                {"key": "guild_id", "type": "string", "size": 36, "required": True},
                {"key": "log_type", "type": "enum", "elements": ['command', 'vote', 'election', 'error', 'admin', 'chancellor_action'], "required": True},
                {"key": "action", "type": "string", "size": 256, "required": True},
                {"key": "discord_id", "type": "string", "size": 36, "required": False},
                {"key": "details", "type": "string", "size": 4096, "required": False},
                {"key": "timestamp", "type": "datetime", "required": True},
                {"key": "severity", "type": "enum", "elements": ['debug', 'info', 'warning', 'error', 'critical'], "required": False, "default": 'info'},
            ]
        }
    ]

    for collection_data in collections:
        try:
            # Check if collection already exists
            try:
                db.get_collection(database_id=database_id, collection_id=collection_data["id"])
                log.warning(f"Collection exists: {collection_data['name']}")
                continue
            except AppwriteException:
                pass  # Collection doesn't exist, proceed to create

            # Create collection
            collection = db.create_collection(
                database_id=database_id,
                collection_id=collection_data["id"],
                name=collection_data["name"],
                permissions=[
                    Permission.read(Role.any()),
                    Permission.write(Role.any()),
                    Permission.update(Role.any()),
                    Permission.delete(Role.any())
                ],
                document_security=True
            )
            log.success(f"Created collection: {collection_data['name']}")

            # Create attributes
            for attr in collection_data["attributes"]:
                key_name = attr.get("key", "<unknown>")
                try:
                    attr_copy = attr.copy()
                    attr_type = attr_copy.pop("type")

                    if attr_type == "string":
                        db.create_string_attribute(database_id, collection_data["id"], **attr_copy)
                    elif attr_type == "integer":
                        db.create_integer_attribute(database_id, collection_data["id"], **attr_copy)
                    elif attr_type == "boolean":
                        db.create_boolean_attribute(database_id, collection_data["id"], **attr_copy)
                    elif attr_type == "datetime":
                        db.create_datetime_attribute(database_id, collection_data["id"], **attr_copy)
                    elif attr_type == "float":
                        db.create_float_attribute(database_id, collection_data["id"], **attr_copy)
                    elif attr_type == "enum":
                        db.create_enum_attribute(database_id, collection_data["id"], **attr_copy)
                    log.success(f"  Created attribute: {key_name}")
                except AppwriteException as e:
                    if "already exists" in str(e).lower():
                        log.warning(f"  Attribute exists: {key_name}")
                    else:
                        log.error(f"  Error creating attribute {key_name}: {str(e)}")
        except AppwriteException as e:
            log.error(f"Error creating collection {collection_data['name']}: {str(e)}")

if __name__ == "__main__":
    log.info("=" * 60)
    log.info("COUNCILLOR BOT - DATABASE MIGRATION SCRIPT")
    log.info("=" * 60)
    log.warning("⚠️  WARNING: This will DELETE ALL existing data!")
    log.warning("⚠️  All collections will be purged and recreated.")
    log.info("=" * 60)

    confirmation = input("\nType 'YES' to confirm and proceed with migration: ")

    if confirmation.strip() != "YES":
        log.info("Migration cancelled.")
        sys.exit(0)

    log.info("\n" + "=" * 60)
    log.info("Starting database migration...")
    log.info("=" * 60 + "\n")

    log.info("Step 1: Creating/finding database...")
    database_id = create_or_get_database()

    if not database_id:
        log.error("Failed to create or find database. Aborting.")
        sys.exit(1)

    log.info("\nStep 2: Purging existing collections...")
    purge_collections(database_id)

    log.info("\nStep 3: Creating new collections...")
    create_collections(database_id)

    log.success("\n" + "=" * 60)
    log.success("✅ Migration complete!")
    log.success("=" * 60)
    log.info("\nYour Appwrite database is now ready to use!")
    log.warning("Note: Indexes and attributes may take a few moments to become fully active.")