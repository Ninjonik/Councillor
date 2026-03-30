#!/usr/bin/env python3
"""
Database migration — creates Appwrite TablesDB tables for Councillor.
Run once against your project (requires API key with databases scope).

Uses appwrite Client raw HTTP (``client.call``) for database/table management so migration
works on Appwrite 1.8.x even when SDK 17’s typed parsers expect newer API fields
(e.g. ``policies`` / ``archives`` on databases).

Uses appwrite>=17 (for ``Client``). Destructive: full purge of existing tables when confirmed.
"""

from __future__ import annotations

import sys

from appwrite.client import Client
from appwrite.exception import AppwriteException
from colorama import Fore, Style, init

try:
    import config
except ImportError:
    print(
        f"{Fore.RED}✗ Error: create config.py from config.example.py with "
        f"APPWRITE_ENDPOINT, APPWRITE_PROJECT, APPWRITE_KEY, APPWRITE_DB_NAME.{Style.RESET_ALL}"
    )
    sys.exit(1)

init(autoreset=True)


class Logger:
    @staticmethod
    def success(msg: str) -> None:
        print(f"{Fore.GREEN}✓ {msg}{Style.RESET_ALL}")

    @staticmethod
    def info(msg: str) -> None:
        print(f"{Fore.CYAN}ℹ {msg}{Style.RESET_ALL}")

    @staticmethod
    def warning(msg: str) -> None:
        print(f"{Fore.YELLOW}⚠ {msg}{Style.RESET_ALL}")

    @staticmethod
    def error(msg: str) -> None:
        print(f"{Fore.RED}✗ {msg}{Style.RESET_ALL}")


log = Logger()

VOTE_TYPE_ELEMENTS = [
    "legislation",
    "amendment",
    "impeachment",
    "confidence_vote",
    "decree",
    "other",
    "election",
    "chancellor_election",
]
STATUS_ELEMENTS = ["pending", "voting", "passed", "failed", "cancelled"]
SETTING_TYPE_ELEMENTS = ["string", "integer", "boolean", "json", "array"]
EDITABLE_BY_ELEMENTS = ["admin", "chancellor", "president"]
LOG_TYPE_ELEMENTS = ["command", "vote", "election", "error", "admin", "chancellor_action"]
SEVERITY_ELEMENTS = ["debug", "info", "warning", "error", "critical"]

TABLE_SPECS: list[dict] = [
    {
        "id": "guilds",
        "name": "Guilds",
        "columns": [
            {"key": "guild_id", "type": "varchar", "size": 36, "required": True},
            {"key": "name", "type": "varchar", "size": 256, "required": True},
            {"key": "description", "type": "varchar", "size": 1024, "required": False},
            {"key": "enabled", "type": "boolean", "required": True, "default": True},
            {"key": "logging_enabled", "type": "boolean", "required": True, "default": True},
            {"key": "voting_channel_id", "type": "varchar", "size": 36, "required": False},
            {"key": "announcement_channel_id", "type": "varchar", "size": 36, "required": False},
            {"key": "councillor_role_id", "type": "varchar", "size": 36, "required": False},
            {"key": "chancellor_role_id", "type": "varchar", "size": 36, "required": False},
            {"key": "minister_role_id", "type": "varchar", "size": 36, "required": False},
            {"key": "president_role_id", "type": "varchar", "size": 36, "required": False},
            {"key": "vice_president_role_id", "type": "varchar", "size": 36, "required": False},
            {"key": "judiciary_role_id", "type": "varchar", "size": 36, "required": False},
            {"key": "citizen_role_id", "type": "varchar", "size": 36, "required": False},
            {"key": "days_requirement", "type": "integer", "required": True, "default": 180},
            {"key": "max_councillors", "type": "integer", "required": True, "default": 9},
        ],
        "indexes": [{"key": "idx_guild_id", "type": "unique", "attributes": ["guild_id"]}],
    },
    {
        "id": "councils",
        "name": "Councils",
        "columns": [
            {"key": "council_id", "type": "varchar", "size": 50, "required": True},
            {"key": "guild_id", "type": "varchar", "size": 36, "required": True},
            {"key": "current_chancellor_id", "type": "varchar", "size": 36, "required": False},
            {"key": "election_in_progress", "type": "boolean", "required": True, "default": False},
        ],
        "indexes": [
            {"key": "idx_council_id", "type": "unique", "attributes": ["council_id"]},
            {"key": "idx_councils_guild", "type": "key", "attributes": ["guild_id"]},
        ],
    },
    {
        "id": "councillors",
        "name": "Councillors",
        "columns": [
            {"key": "discord_id", "type": "varchar", "size": 36, "required": True},
            {"key": "name", "type": "varchar", "size": 256, "required": True},
            {"key": "council_id", "type": "varchar", "size": 50, "required": True},
            {"key": "joined_at", "type": "datetime", "required": True},
            {"key": "active", "type": "boolean", "required": True, "default": True},
            {"key": "is_chancellor", "type": "boolean", "required": True, "default": False},
            {"key": "ministry_ids", "type": "varchar", "size": 100, "required": False, "array": True},
        ],
        "indexes": [
            {"key": "idx_councillors_discord_council", "type": "unique", "attributes": ["discord_id", "council_id"]},
            {"key": "idx_councillors_council", "type": "key", "attributes": ["council_id"]},
        ],
    },
    {
        "id": "ministries",
        "name": "Ministries",
        "columns": [
            {"key": "name", "type": "varchar", "size": 256, "required": True},
            {"key": "description", "type": "varchar", "size": 1024, "required": False},
            {"key": "council_id", "type": "varchar", "size": 50, "required": True},
            {"key": "minister_discord_id", "type": "varchar", "size": 36, "required": False},
            {"key": "role_ids", "type": "varchar", "size": 36, "required": False, "array": True},
            {"key": "created_by", "type": "varchar", "size": 36, "required": False},
            {"key": "created_at", "type": "datetime", "required": True},
            {"key": "active", "type": "boolean", "required": True, "default": True},
        ],
        "indexes": [{"key": "idx_ministries_council", "type": "key", "attributes": ["council_id"]}],
    },
    {
        "id": "votings",
        "name": "Votings",
        "columns": [
            {"key": "type", "type": "enum", "elements": VOTE_TYPE_ELEMENTS, "required": True},
            {"key": "status", "type": "enum", "elements": STATUS_ELEMENTS, "required": True},
            {"key": "title", "type": "varchar", "size": 512, "required": True},
            {"key": "description", "type": "mediumtext", "required": False},
            {"key": "council_id", "type": "varchar", "size": 50, "required": True},
            {"key": "proposer_id", "type": "varchar", "size": 36, "required": False},
            {"key": "message_id", "type": "varchar", "size": 36, "required": False},
            {"key": "voting_start", "type": "datetime", "required": False},
            {"key": "voting_end", "type": "datetime", "required": True},
            {"key": "required_percentage", "type": "float", "required": True, "default": 0.5},
            {"key": "result_announced", "type": "boolean", "required": True, "default": False},
        ],
        "indexes": [
            {"key": "idx_votings_council", "type": "key", "attributes": ["council_id"]},
            {"key": "idx_votings_status", "type": "key", "attributes": ["status"]},
            {"key": "idx_votings_end", "type": "key", "attributes": ["voting_end"]},
        ],
    },
    {
        "id": "votes",
        "name": "Votes",
        "columns": [
            {"key": "voting_id", "type": "varchar", "size": 36, "required": True},
            {"key": "councillor_id", "type": "varchar", "size": 36, "required": False},
            {"key": "discord_id", "type": "varchar", "size": 36, "required": False},
            {"key": "stance", "type": "boolean", "required": True},
            {"key": "candidate_id", "type": "varchar", "size": 36, "required": False},
            {"key": "voted_at", "type": "datetime", "required": True},
        ],
        "indexes": [
            {"key": "idx_votes_voting", "type": "key", "attributes": ["voting_id"]},
            {"key": "idx_votes_councillor", "type": "key", "attributes": ["councillor_id"]},
            {"key": "idx_votes_discord", "type": "key", "attributes": ["discord_id"]},
        ],
    },
    {
        "id": "election_candidates",
        "name": "Election Candidates",
        "columns": [
            {"key": "voting_id", "type": "varchar", "size": 36, "required": True},
            {"key": "discord_id", "type": "varchar", "size": 36, "required": True},
            {"key": "name", "type": "varchar", "size": 256, "required": True},
            {"key": "registered_at", "type": "datetime", "required": True},
            {"key": "vote_count", "type": "integer", "required": True, "default": 0},
            {"key": "elected", "type": "boolean", "required": True, "default": False},
        ],
        "indexes": [
            {"key": "idx_ecand_voting", "type": "key", "attributes": ["voting_id"]},
            {"key": "idx_ecand_voting_discord", "type": "unique", "attributes": ["voting_id", "discord_id"]},
        ],
    },
    {
        "id": "registered_voters",
        "name": "Registered Voters",
        "columns": [
            {"key": "voting_id", "type": "varchar", "size": 36, "required": True},
            {"key": "discord_id", "type": "varchar", "size": 36, "required": True},
            {"key": "name", "type": "varchar", "size": 256, "required": True},
            {"key": "registered_at", "type": "datetime", "required": True},
            {"key": "has_voted", "type": "boolean", "required": True, "default": False},
        ],
        "indexes": [
            {"key": "idx_regv_voting", "type": "key", "attributes": ["voting_id"]},
            {"key": "idx_regv_voting_discord", "type": "unique", "attributes": ["voting_id", "discord_id"]},
        ],
    },
    {
        "id": "settings",
        "name": "Settings",
        "columns": [
            {"key": "key", "type": "varchar", "size": 256, "required": True},
            {"key": "value", "type": "mediumtext", "required": True},
            {"key": "type", "type": "enum", "elements": SETTING_TYPE_ELEMENTS, "required": True},
            {"key": "description", "type": "varchar", "size": 512, "required": False},
            {"key": "guild_id", "type": "varchar", "size": 36, "required": False},
            {"key": "editable_by", "type": "enum", "elements": EDITABLE_BY_ELEMENTS, "required": True, "default": "admin"},
        ],
        "indexes": [
            {"key": "idx_settings_key", "type": "key", "attributes": ["key"]},
            {"key": "idx_settings_key_guild", "type": "unique", "attributes": ["key", "guild_id"]},
        ],
    },
    {
        "id": "logs",
        "name": "Logs",
        "columns": [
            {"key": "guild_id", "type": "varchar", "size": 36, "required": True},
            {"key": "log_type", "type": "enum", "elements": LOG_TYPE_ELEMENTS, "required": True},
            {"key": "action", "type": "varchar", "size": 256, "required": True},
            {"key": "discord_id", "type": "varchar", "size": 36, "required": False},
            {"key": "details", "type": "mediumtext", "required": False},
            {"key": "timestamp", "type": "datetime", "required": True},
            {"key": "severity", "type": "enum", "elements": SEVERITY_ELEMENTS, "required": True, "default": "info"},
        ],
        "indexes": [
            {"key": "idx_logs_guild", "type": "key", "attributes": ["guild_id"]},
            {"key": "idx_logs_ts", "type": "key", "attributes": ["timestamp"]},
        ],
    },
]


def _database_id_from_config() -> str | None:
    """Optional explicit database $id (skip discovery)."""
    return getattr(config, "APPWRITE_DATABASE_ID", None) or None


def find_database_id_by_name_raw(client: Client, database_name: str) -> str | None:
    try:
        data = client.call("get", "/tablesdb", {}, {})
    except AppwriteException as e:
        log.error(f"Failed to list databases: {e!s}")
        return None
    for d in data.get("databases") or []:
        if d.get("name") == database_name:
            return d.get("$id")
    return None


def create_or_get_database_raw(client: Client) -> str | None:
    explicit = _database_id_from_config()
    if explicit:
        log.info(f"Using APPWRITE_DATABASE_ID from config: {explicit}")
        return explicit

    name = config.APPWRITE_DB_NAME
    found_id = find_database_id_by_name_raw(client, name)
    if found_id:
        log.info(f"Using existing database: {name} (ID: {found_id})")
        return found_id

    safe_id = name.lower().replace(" ", "_")
    try:
        client.call(
            "post",
            "/tablesdb",
            {"content-type": "application/json"},
            {"databaseId": safe_id, "name": name},
        )
        log.success(f"Created database: {name} (ID: {safe_id})")
        return safe_id
    except AppwriteException as e:
        err = str(e).lower()
        code = getattr(e, "code", None)
        if "already exists" in err or code == 409:
            retry = find_database_id_by_name_raw(client, name)
            if retry:
                log.info(f"Database already exists, using ID: {retry}")
                return retry
            log.warning(
                f"Database reported as existing but list did not return it; using ID {safe_id!r}"
            )
            return safe_id
        log.error(f"Failed to create database: {e!s}")
        return None


def purge_tables_raw(client: Client, database_id: str) -> None:
    try:
        data = client.call("get", f"/tablesdb/{database_id}/tables", {}, {})
    except AppwriteException as e:
        log.warning(f"Could not list tables (maybe empty): {e!s}")
        return
    for t in data.get("tables") or []:
        tid = t.get("$id")
        if not tid:
            continue
        try:
            client.call(
                "delete",
                f"/tablesdb/{database_id}/tables/{tid}",
                {"content-type": "application/json"},
                {},
            )
            log.success(f"Deleted table: {tid}")
        except AppwriteException as e:
            if "not found" in str(e).lower() or "404" in str(e):
                log.info(f"Table not found (skip): {tid}")
            else:
                log.warning(f"Error deleting table {tid}: {e!s}")


def _table_exists_raw(client: Client, database_id: str, table_id: str) -> bool:
    try:
        client.call("get", f"/tablesdb/{database_id}/tables/{table_id}", {}, {})
        return True
    except AppwriteException:
        return False


def create_tables_raw(client: Client, database_id: str) -> None:
    for spec in TABLE_SPECS:
        if _table_exists_raw(client, database_id, spec["id"]):
            log.warning(f"Table already exists: {spec['name']}")
            continue
        try:
            client.call(
                "post",
                f"/tablesdb/{database_id}/tables",
                {"content-type": "application/json"},
                {
                    "tableId": spec["id"],
                    "name": spec["name"],
                    "columns": spec["columns"],
                    "indexes": spec.get("indexes") or [],
                },
            )
            log.success(f"Created table: {spec['name']}")
        except AppwriteException as e:
            log.error(f"Failed to create table {spec['name']}: {e!s}")


if __name__ == "__main__":
    log.info("=" * 60)
    log.info("COUNCILLOR BOT — TablesDB migration")
    log.info("=" * 60)
    log.warning("⚠️  WARNING: This will DELETE ALL TABLES in this database if you confirm!")
    log.info("=" * 60)

    confirmation = input("\nType 'YES' to confirm purge + recreate tables: ")
    if confirmation.strip() != "YES":
        log.info("Migration cancelled.")
        sys.exit(0)

    client = Client()
    client.set_endpoint(config.APPWRITE_ENDPOINT)
    client.set_project(config.APPWRITE_PROJECT)
    client.set_key(config.APPWRITE_KEY)

    log.info("\nStep 1: Database...")
    database_id = create_or_get_database_raw(client)
    if not database_id:
        log.error("Aborting.")
        sys.exit(1)

    log.info("\nStep 2: Purge existing tables...")
    purge_tables_raw(client, database_id)

    log.info("\nStep 3: Create tables...")
    create_tables_raw(client, database_id)

    log.success("\n" + "=" * 60)
    log.success("Migration finished (indexes/columns may take a moment to activate).")
    log.success("=" * 60)
