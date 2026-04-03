from __future__ import annotations

import sys
import time

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
    "legislation", "amendment", "impeachment", "confidence_vote",
    "decree", "other", "election", "chancellor_election",
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
            {"key": "guild_id",                 "type": "varchar",  "size": 36,   "required": True},
            {"key": "name",                     "type": "varchar",  "size": 256,  "required": True},
            {"key": "description",              "type": "varchar",  "size": 1024, "required": False},
            {"key": "enabled",                  "type": "boolean",                "required": True,  "default": True},
            {"key": "logging_enabled",          "type": "boolean",                "required": True,  "default": True},
            {"key": "voting_channel_id",        "type": "varchar",  "size": 36,   "required": False},
            {"key": "announcement_channel_id",  "type": "varchar",  "size": 36,   "required": False},
            {"key": "councillor_role_id",       "type": "varchar",  "size": 36,   "required": False},
            {"key": "chancellor_role_id",       "type": "varchar",  "size": 36,   "required": False},
            {"key": "minister_role_id",         "type": "varchar",  "size": 36,   "required": False},
            {"key": "president_role_id",        "type": "varchar",  "size": 36,   "required": False},
            {"key": "vice_president_role_id",   "type": "varchar",  "size": 36,   "required": False},
            {"key": "judiciary_role_id",        "type": "varchar",  "size": 36,   "required": False},
            {"key": "citizen_role_id",          "type": "varchar",  "size": 36,   "required": False},
            {"key": "days_requirement",         "type": "integer",                "required": True,  "default": 180},
            {"key": "max_councillors",          "type": "integer",                "required": True,  "default": 9},
        ],
        "indexes": [{"key": "idx_guild_id", "type": "unique", "attributes": ["guild_id"]}],
    },
    {
        "id": "councils",
        "name": "Councils",
        "columns": [
            {"key": "council_id",           "type": "varchar", "size": 50, "required": True},
            {"key": "guild_id",             "type": "varchar", "size": 36, "required": True},
            {"key": "current_chancellor_id","type": "varchar", "size": 36, "required": False},
            {"key": "election_in_progress", "type": "boolean",             "required": True, "default": False},
        ],
        "indexes": [
            {"key": "idx_council_id",    "type": "unique", "attributes": ["council_id"]},
            {"key": "idx_councils_guild","type": "key",    "attributes": ["guild_id"]},
        ],
    },
    {
        "id": "councillors",
        "name": "Councillors",
        "columns": [
            {"key": "discord_id",   "type": "varchar",  "size": 36,  "required": True},
            {"key": "name",         "type": "varchar",  "size": 256, "required": True},
            {"key": "council_id",   "type": "varchar",  "size": 50,  "required": True},
            {"key": "joined_at",    "type": "datetime",              "required": True},
            {"key": "active",       "type": "boolean",               "required": True,  "default": True},
            {"key": "is_chancellor","type": "boolean",               "required": True,  "default": False},
            {"key": "ministry_ids", "type": "varchar",  "size": 100, "required": False, "array": True},
        ],
        "indexes": [
            {"key": "idx_councillors_discord_council", "type": "unique", "attributes": ["discord_id", "council_id"]},
            {"key": "idx_councillors_council",         "type": "key",    "attributes": ["council_id"]},
        ],
    },
    {
        "id": "ministries",
        "name": "Ministries",
        "columns": [
            {"key": "name",               "type": "varchar",  "size": 256,  "required": True},
            {"key": "description",        "type": "varchar",  "size": 1024, "required": False},
            {"key": "council_id",         "type": "varchar",  "size": 50,   "required": True},
            {"key": "minister_discord_id","type": "varchar",  "size": 36,   "required": False},
            {"key": "role_ids",           "type": "varchar",  "size": 36,   "required": False, "array": True},
            {"key": "created_by",         "type": "varchar",  "size": 36,   "required": False},
            {"key": "created_at",         "type": "datetime",               "required": True},
            {"key": "active",             "type": "boolean",                "required": True, "default": True},
        ],
        "indexes": [{"key": "idx_ministries_council", "type": "key", "attributes": ["council_id"]}],
    },
    {
        "id": "votings",
        "name": "Votings",
        "columns": [
            {"key": "type",                "type": "enum",       "elements": VOTE_TYPE_ELEMENTS, "required": True},
            {"key": "status",              "type": "enum",       "elements": STATUS_ELEMENTS,    "required": True},
            {"key": "title",               "type": "varchar",    "size": 512,  "required": True},
            {"key": "description",         "type": "mediumtext",               "required": False},
            {"key": "council_id",          "type": "varchar",    "size": 50,   "required": True},
            {"key": "proposer_id",         "type": "varchar",    "size": 36,   "required": False},
            {"key": "message_id",          "type": "varchar",    "size": 36,   "required": False},
            {"key": "voting_start",        "type": "datetime",                 "required": False},
            {"key": "voting_end",          "type": "datetime",                 "required": True},
            {"key": "required_percentage", "type": "float",                    "required": True, "default": 0.5},
            {"key": "result_announced",    "type": "boolean",                  "required": True, "default": False},
        ],
        "indexes": [
            {"key": "idx_votings_council", "type": "key", "attributes": ["council_id"]},
            {"key": "idx_votings_status",  "type": "key", "attributes": ["status"]},
            {"key": "idx_votings_end",     "type": "key", "attributes": ["voting_end"]},
        ],
    },
    {
        "id": "votes",
        "name": "Votes",
        "columns": [
            {"key": "voting_id",     "type": "varchar",  "size": 36, "required": True},
            {"key": "councillor_id", "type": "varchar",  "size": 36, "required": False},
            {"key": "discord_id",    "type": "varchar",  "size": 36, "required": False},
            {"key": "stance",        "type": "boolean",              "required": True},
            {"key": "candidate_id",  "type": "varchar",  "size": 36, "required": False},
            {"key": "voted_at",      "type": "datetime",             "required": True},
        ],
        "indexes": [
            {"key": "idx_votes_voting",      "type": "key", "attributes": ["voting_id"]},
            {"key": "idx_votes_councillor",  "type": "key", "attributes": ["councillor_id"]},
            {"key": "idx_votes_discord",     "type": "key", "attributes": ["discord_id"]},
        ],
    },
    {
        "id": "election_candidates",
        "name": "Election Candidates",
        "columns": [
            {"key": "voting_id",     "type": "varchar",  "size": 36,  "required": True},
            {"key": "discord_id",    "type": "varchar",  "size": 36,  "required": True},
            {"key": "name",          "type": "varchar",  "size": 256, "required": True},
            {"key": "registered_at", "type": "datetime",              "required": True},
            {"key": "vote_count",    "type": "integer",               "required": True, "default": 0},
            {"key": "elected",       "type": "boolean",               "required": True, "default": False},
        ],
        "indexes": [
            {"key": "idx_ecand_voting",        "type": "key",    "attributes": ["voting_id"]},
            {"key": "idx_ecand_voting_discord","type": "unique", "attributes": ["voting_id", "discord_id"]},
        ],
    },
    {
        "id": "registered_voters",
        "name": "Registered Voters",
        "columns": [
            {"key": "voting_id",     "type": "varchar",  "size": 36,  "required": True},
            {"key": "discord_id",    "type": "varchar",  "size": 36,  "required": True},
            {"key": "name",          "type": "varchar",  "size": 256, "required": True},
            {"key": "registered_at", "type": "datetime",              "required": True},
            {"key": "has_voted",     "type": "boolean",               "required": True, "default": False},
        ],
        "indexes": [
            {"key": "idx_regv_voting",        "type": "key",    "attributes": ["voting_id"]},
            {"key": "idx_regv_voting_discord","type": "unique", "attributes": ["voting_id", "discord_id"]},
        ],
    },
    {
        "id": "settings",
        "name": "Settings",
        "columns": [
            {"key": "key",         "type": "varchar",    "size": 256, "required": True},
            {"key": "value",       "type": "mediumtext",              "required": True},
            {"key": "type",        "type": "enum",  "elements": SETTING_TYPE_ELEMENTS, "required": True},
            {"key": "description", "type": "varchar",    "size": 512, "required": False},
            {"key": "guild_id",    "type": "varchar",    "size": 36,  "required": False},
            {"key": "editable_by", "type": "enum",  "elements": EDITABLE_BY_ELEMENTS, "required": True, "default": "admin"},
        ],
        "indexes": [
            {"key": "idx_settings_key",       "type": "key",    "attributes": ["key"]},
            {"key": "idx_settings_key_guild", "type": "unique", "attributes": ["key", "guild_id"]},
        ],
    },
    {
        "id": "logs",
        "name": "Logs",
        "columns": [
            {"key": "guild_id",  "type": "varchar",  "size": 36,  "required": True},
            {"key": "log_type",  "type": "enum",  "elements": LOG_TYPE_ELEMENTS,  "required": True},
            {"key": "action",    "type": "varchar",  "size": 256, "required": True},
            {"key": "discord_id","type": "varchar",  "size": 36,  "required": False},
            {"key": "details",   "type": "mediumtext",             "required": False},
            {"key": "timestamp", "type": "datetime",               "required": True},
            {"key": "severity",  "type": "enum",  "elements": SEVERITY_ELEMENTS, "required": True, "default": "info"},
        ],
        "indexes": [
            {"key": "idx_logs_guild", "type": "key", "attributes": ["guild_id"]},
            {"key": "idx_logs_ts",    "type": "key", "attributes": ["timestamp"]},
        ],
    },
    {
        "id": "decrees",
        "name": "Decrees",
        "columns": [
            {"key": "guild_id",       "type": "varchar",  "size": 36,  "required": True},
            {"key": "title",          "type": "varchar",  "size": 512, "required": True},
            {"key": "description",    "type": "mediumtext",              "required": False},
            {"key": "issued_by",      "type": "varchar",  "size": 36,  "required": True},
            {"key": "issued_by_name", "type": "varchar",  "size": 256, "required": True},
            {"key": "issued_at",      "type": "datetime",               "required": True},
            {"key": "expires_at",     "type": "datetime",               "required": False},
            {"key": "active",         "type": "boolean",                "required": True, "default": True},
            {"key": "revoked_at",     "type": "datetime",               "required": False},
            {"key": "revoke_reason",  "type": "varchar",  "size": 512, "required": False},
        ],
        "indexes": [
            {"key": "idx_decrees_guild", "type": "key", "attributes": ["guild_id"]},
            {"key": "idx_decrees_active", "type": "key", "attributes": ["active"]},
            {"key": "idx_decrees_exp", "type": "key", "attributes": ["expires_at"]},
        ],
    },
]


def _database_id_from_config() -> str | None:
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
            "post", "/tablesdb",
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
            log.warning(f"Database reported as existing but list did not return it; using ID {safe_id!r}")
            return safe_id
        log.error(f"Failed to create database: {e!s}")
        return None


def _extract_key(item: dict, *candidates: str) -> str | None:
    for candidate in candidates:
        value = item.get(candidate)
        if value:
            return str(value)
    return None


def _table_exists_raw(client: Client, database_id: str, table_id: str) -> bool:
    try:
        client.call("get", f"/tablesdb/{database_id}/tables/{table_id}", {}, {})
        return True
    except AppwriteException:
        return False


def _list_columns_raw(client: Client, database_id: str, table_id: str) -> dict[str, dict]:
    try:
        data = client.call("get", f"/tablesdb/{database_id}/tables/{table_id}/columns", {}, {})
    except AppwriteException:
        return {}

    out: dict[str, dict] = {}
    for col in data.get("columns") or []:
        key = _extract_key(col, "key", "$id", "id")
        if key:
            out[key] = col
    return out


def _list_indexes_raw(client: Client, database_id: str, table_id: str) -> dict[str, dict]:
    try:
        data = client.call("get", f"/tablesdb/{database_id}/tables/{table_id}/indexes", {}, {})
    except AppwriteException:
        return {}

    out: dict[str, dict] = {}
    for idx in data.get("indexes") or []:
        key = _extract_key(idx, "key", "$id", "id")
        if key:
            out[key] = idx
    return out


def _create_table_raw(client: Client, database_id: str, table_id: str, name: str) -> bool:
    try:
        client.call(
            "post",
            f"/tablesdb/{database_id}/tables",
            {"content-type": "application/json"},
            {"tableId": table_id, "name": name},
        )
        log.success(f"Created table: {name}")
        return True
    except AppwriteException as e:
        log.error(f"Failed to create table {name}: {e!s}")
        return False


def _create_index_raw(client: Client, database_id: str, table_id: str, idx: dict) -> None:
    client.call(
        "post",
        f"/tablesdb/{database_id}/tables/{table_id}/indexes",
        {"content-type": "application/json"},
        {
            "key": idx["key"],
            "type": idx["type"],
            "columns": idx["attributes"],
        },
    )


def _delete_column_raw(client: Client, database_id: str, table_id: str, column_key: str) -> None:
    client.call(
        "delete",
        f"/tablesdb/{database_id}/tables/{table_id}/columns/{column_key}",
        {"content-type": "application/json"},
        {},
    )


def _create_column(client: Client, database_id: str, table_id: str, col: dict) -> None:
    key = col["key"]
    ctype = col["type"]
    required = col.get("required", False)
    default = col.get("default", None)
    is_array = col.get("array", False)
    headers = {"content-type": "application/json"}
    base = f"/tablesdb/{database_id}/tables/{table_id}/columns"

    # Appwrite does not allow default + required=True simultaneously.
    # If a default is set, the column must be required=False.
    if default is not None and required:
        required = False

    if ctype == "varchar":
        body: dict = {"key": key, "size": col["size"], "required": required, "array": is_array}
        if default is not None:
            body["default"] = default
        client.call("post", f"{base}/varchar", headers, body)

    elif ctype in ("text", "mediumtext", "longtext"):
        body = {"key": key, "required": required, "array": is_array}
        if default is not None:
            body["default"] = default
        client.call("post", f"{base}/{ctype}", headers, body)

    elif ctype == "enum":
        body = {"key": key, "elements": col["elements"], "required": required, "array": is_array}
        if default is not None:
            body["default"] = default
        client.call("post", f"{base}/enum", headers, body)

    elif ctype == "boolean":
        body = {"key": key, "required": required, "array": is_array}
        if default is not None:
            body["default"] = default
        client.call("post", f"{base}/boolean", headers, body)

    elif ctype == "integer":
        body = {"key": key, "required": required, "array": is_array}
        if default is not None:
            body["default"] = default
        client.call("post", f"{base}/integer", headers, body)

    elif ctype == "float":
        body = {"key": key, "required": required, "array": is_array}
        if default is not None:
            body["default"] = default
        client.call("post", f"{base}/float", headers, body)

    elif ctype == "datetime":
        body = {"key": key, "required": required, "array": is_array}
        if default is not None:
            body["default"] = default
        client.call("post", f"{base}/datetime", headers, body)

    else:
        raise ValueError(f"Unknown column type: {ctype!r} for key {key!r}")


def _warn_column_drift(table_name: str, key: str, desired: dict, live: dict) -> None:
    desired_required = bool(desired.get("required", False))
    desired_array = bool(desired.get("array", False))
    live_required = bool(live.get("required", False))
    live_array = bool(live.get("array", False))

    live_type = str(live.get("type") or "").lower()
    desired_type = str(desired.get("type") or "").lower()

    drift_fields: list[str] = []
    if live_type and live_type != desired_type:
        drift_fields.append(f"type live={live_type} desired={desired_type}")
    if live_required != desired_required:
        drift_fields.append(f"required live={live_required} desired={desired_required}")
    if live_array != desired_array:
        drift_fields.append(f"array live={live_array} desired={desired_array}")

    if desired_type == "varchar":
        live_size = live.get("size")
        desired_size = desired.get("size")
        if live_size is not None and desired_size is not None and int(live_size) != int(desired_size):
            drift_fields.append(f"size live={live_size} desired={desired_size}")

    if drift_fields:
        log.warning(f"Schema drift on {table_name}.{key}: " + ", ".join(drift_fields))


def sync_schema_raw(client: Client, database_id: str) -> None:
    for spec in TABLE_SPECS:
        table_id = spec["id"]
        table_name = spec["name"]

        if not _table_exists_raw(client, database_id, table_id):
            if not _create_table_raw(client, database_id, table_id, table_name):
                continue
            time.sleep(0.5)

        live_columns = _list_columns_raw(client, database_id, table_id)
        desired_columns = {col["key"]: col for col in spec.get("columns") or []}

        # Create missing columns.
        for col_key, col_spec in desired_columns.items():
            if col_key in live_columns:
                _warn_column_drift(table_name, col_key, col_spec, live_columns[col_key])
                continue
            try:
                _create_column(client, database_id, table_id, col_spec)
                log.success(f"  + column {col_key} ({col_spec['type']})")
            except AppwriteException as e:
                log.error(f"  ✗ column {col_key} on {table_name}: {e!s}")

        # Prompt before dropping extra columns that are not in TABLE_SPECS.
        extra_columns = sorted(set(live_columns.keys()) - set(desired_columns.keys()))
        if extra_columns:
            log.warning(f"Extra columns in {table_name}: {', '.join(extra_columns)}")
            answer = input(
                f"Drop extra columns from {table_name}? This can destroy data. Type 'DROP' to confirm: "
            ).strip()
            if answer == "DROP":
                for extra_key in extra_columns:
                    try:
                        _delete_column_raw(client, database_id, table_id, extra_key)
                        log.success(f"  - dropped column {extra_key}")
                    except AppwriteException as e:
                        log.error(f"  ✗ failed dropping column {extra_key} on {table_name}: {e!s}")
            else:
                log.info(f"Skipped dropping extra columns on {table_name}")

        # Create missing indexes and warn on index drift.
        live_indexes = _list_indexes_raw(client, database_id, table_id)
        desired_indexes = {idx["key"]: idx for idx in spec.get("indexes") or []}

        for idx_key, idx_spec in desired_indexes.items():
            live_idx = live_indexes.get(idx_key)
            if not live_idx:
                try:
                    _create_index_raw(client, database_id, table_id, idx_spec)
                    log.success(f"  + index {idx_key}")
                except AppwriteException as e:
                    log.error(f"  ✗ index {idx_key} on {table_name}: {e!s}")
                continue

            live_type = str(live_idx.get("type") or "")
            desired_type = str(idx_spec.get("type") or "")
            live_cols = list(live_idx.get("attributes") or live_idx.get("columns") or [])
            desired_cols = list(idx_spec.get("attributes") or [])
            if live_type != desired_type or live_cols != desired_cols:
                log.warning(
                    f"Index drift on {table_name}.{idx_key}: "
                    f"live type={live_type} cols={live_cols}, desired type={desired_type} cols={desired_cols}"
                )


if __name__ == "__main__":
    log.info("=" * 60)
    log.info("COUNCILLOR BOT — TablesDB schema sync")
    log.info("=" * 60)
    log.info("This migration is additive and non-destructive by default.")
    log.info("It creates missing tables/columns/indexes and only asks before dropping extra columns.")
    log.info("=" * 60)

    client = Client()
    client.set_endpoint(config.APPWRITE_ENDPOINT)
    client.set_project(config.APPWRITE_PROJECT)
    client.set_key(config.APPWRITE_KEY)

    log.info("\nStep 1: Database...")
    database_id = create_or_get_database_raw(client)
    if not database_id:
        log.error("Aborting.")
        sys.exit(1)

    log.info("\nStep 2: Sync tables + columns + indexes...")
    sync_schema_raw(client, database_id)

    log.success("\n" + "=" * 60)
    log.success("Schema sync finished.")
    log.success("=" * 60)

