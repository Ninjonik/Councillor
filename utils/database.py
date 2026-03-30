"""
Database helper functions for Appwrite TablesDB operations
Provides a clean interface for database operations with error handling
"""
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from appwrite.query import Query
from appwrite.services.tables_db import TablesDB
from appwrite.exception import AppwriteException
from appwrite.id import ID

import config
from utils.enums import VotingType, VotingStatus, LogType, LogSeverity


def row_to_doc(row: Any) -> Dict[str, Any]:
    """Flatten Appwrite Tables row to legacy document dict ($id + column attributes)."""
    if row is None:
        return {}
    if isinstance(row, dict):
        return row
    data = getattr(row, "data", None)
    if not isinstance(data, dict):
        data = {}
    rid = getattr(row, "id", None)
    if rid is None and hasattr(row, "model_dump"):
        dumped = row.model_dump(by_alias=True)
        rid = dumped.get("$id") or dumped.get("id")
    out = {**data}
    if rid is not None:
        out["$id"] = rid
    return out


def wrap_list_rows(result: Any) -> Dict[str, Any]:
    """Match legacy list_documents response shape ({documents, total})."""
    rows = getattr(result, "rows", None) or []
    docs = [row_to_doc(r) for r in rows]
    total = int(getattr(result, "total", 0) or 0)
    return {"documents": docs, "total": total}


class DatabaseHelper:
    """Helper class for database operations (Appwrite TablesDB)."""

    def __init__(self, tables: TablesDB):
        self.tables = tables
        self.db_id = config.APPWRITE_DB_NAME

    # ============================================
    # Guild Operations
    # ============================================

    async def get_guild(self, guild_id: int | str) -> Optional[Dict[str, Any]]:
        """Get guild data by ID"""
        try:
            row = self.tables.get_row(
                database_id=self.db_id,
                table_id="guilds",
                row_id=str(guild_id),
            )
            return row_to_doc(row)
        except AppwriteException:
            return None

    async def create_guild(self, guild_id: int | str, name: str, description: str = "") -> Dict[str, Any]:
        """Create a new guild record"""
        council_id = f"{guild_id}_c"

        self.tables.create_row(
            database_id=self.db_id,
            table_id="councils",
            row_id=council_id,
            data={
                "council_id": council_id,
                "guild_id": str(guild_id),
                "election_in_progress": False,
            },
        )

        guild = self.tables.create_row(
            database_id=self.db_id,
            table_id="guilds",
            row_id=str(guild_id),
            data={
                "guild_id": str(guild_id),
                "name": name,
                "description": description or "",
                "enabled": True,
                "logging_enabled": True,
                "days_requirement": 180,
                "max_councillors": 9,
            },
        )

        return row_to_doc(guild)

    async def update_guild(self, guild_id: int | str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update guild data"""
        row = self.tables.update_row(
            database_id=self.db_id,
            table_id="guilds",
            row_id=str(guild_id),
            data=data,
        )
        return row_to_doc(row)

    async def delete_guild(self, guild_id: int | str) -> bool:
        """Delete a guild and its associated data"""
        try:
            self.tables.delete_row(
                database_id=self.db_id,
                table_id="guilds",
                row_id=str(guild_id),
            )

            council_id = f"{guild_id}_c"
            self.tables.delete_row(
                database_id=self.db_id,
                table_id="councils",
                row_id=council_id,
            )

            return True
        except AppwriteException:
            return False

    # ============================================
    # Council Operations
    # ============================================

    async def get_council(self, guild_id: int | str) -> Optional[Dict[str, Any]]:
        """Get council data for a guild"""
        try:
            council_id = f"{guild_id}_c"
            row = self.tables.get_row(
                database_id=self.db_id,
                table_id="councils",
                row_id=council_id,
            )
            return row_to_doc(row)
        except AppwriteException:
            return None

    async def update_council(self, guild_id: int | str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update council data"""
        council_id = f"{guild_id}_c"
        row = self.tables.update_row(
            database_id=self.db_id,
            table_id="councils",
            row_id=council_id,
            data=data,
        )
        return row_to_doc(row)

    # ============================================
    # Councillor Operations
    # ============================================

    async def get_councillor(self, discord_id: int | str, guild_id: int | str) -> Optional[Dict[str, Any]]:
        """Get councillor data"""
        try:
            council_id = f"{guild_id}_c"
            result = self.tables.list_rows(
                database_id=self.db_id,
                table_id="councillors",
                queries=[
                    Query.equal("discord_id", str(discord_id)),
                    Query.equal("council_id", council_id),
                    Query.limit(1),
                ],
            )
            wrapped = wrap_list_rows(result)
            if wrapped["total"] > 0:
                return wrapped["documents"][0]
            return None
        except AppwriteException:
            return None

    async def create_councillor(
        self,
        discord_id: int | str,
        name: str,
        guild_id: int | str,
    ) -> Dict[str, Any]:
        """Create a new councillor"""
        council_id = f"{guild_id}_c"
        row = self.tables.create_row(
            database_id=self.db_id,
            table_id="councillors",
            row_id=ID.unique(),
            data={
                "discord_id": str(discord_id),
                "name": name,
                "council_id": council_id,
                "joined_at": datetime.now(timezone.utc).isoformat(),
                "active": True,
                "is_chancellor": False,
            },
        )
        return row_to_doc(row)

    async def list_councillors(self, guild_id: int | str, active_only: bool = True) -> List[Dict[str, Any]]:
        """List all councillors for a guild"""
        council_id = f"{guild_id}_c"
        queries = [Query.equal("council_id", council_id)]

        if active_only:
            queries.append(Query.equal("active", True))

        result = self.tables.list_rows(
            database_id=self.db_id,
            table_id="councillors",
            queries=queries,
        )
        return wrap_list_rows(result)["documents"]

    async def update_councillor(self, councillor_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update councillor data"""
        row = self.tables.update_row(
            database_id=self.db_id,
            table_id="councillors",
            row_id=councillor_id,
            data=data,
        )
        return row_to_doc(row)

    async def deactivate_councillor(self, discord_id: int | str, guild_id: int | str) -> bool:
        """Deactivate a councillor"""
        try:
            councillor = await self.get_councillor(discord_id, guild_id)
            if councillor:
                await self.update_councillor(councillor["$id"], {"active": False})
                return True
            return False
        except AppwriteException:
            return False

    # ============================================
    # Ministry Operations
    # ============================================

    async def create_ministry(
        self,
        name: str,
        description: str,
        guild_id: int | str,
        created_by: int | str,
        minister_discord_id: Optional[int | str] = None,
    ) -> Dict[str, Any]:
        """Create a new ministry"""
        council_id = f"{guild_id}_c"
        data: Dict[str, Any] = {
            "name": name,
            "description": description,
            "council_id": council_id,
            "created_by": str(created_by),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "active": True,
        }

        if minister_discord_id:
            data["minister_discord_id"] = str(minister_discord_id)

        row = self.tables.create_row(
            database_id=self.db_id,
            table_id="ministries",
            row_id=ID.unique(),
            data=data,
        )
        return row_to_doc(row)

    async def list_ministries(self, guild_id: int | str, active_only: bool = True) -> List[Dict[str, Any]]:
        """List all ministries for a guild"""
        council_id = f"{guild_id}_c"
        queries = [Query.equal("council_id", council_id)]

        if active_only:
            queries.append(Query.equal("active", True))

        result = self.tables.list_rows(
            database_id=self.db_id,
            table_id="ministries",
            queries=queries,
        )
        return wrap_list_rows(result)["documents"]

    async def update_ministry(self, ministry_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update ministry data"""
        row = self.tables.update_row(
            database_id=self.db_id,
            table_id="ministries",
            row_id=ministry_id,
            data=data,
        )
        return row_to_doc(row)

    async def delete_ministry(self, ministry_id: str) -> bool:
        """Delete a ministry"""
        try:
            self.tables.delete_row(
                database_id=self.db_id,
                table_id="ministries",
                row_id=ministry_id,
            )
            return True
        except AppwriteException:
            return False

    # ============================================
    # Voting Operations
    # ============================================

    async def create_voting(
        self,
        voting_type: VotingType,
        title: str,
        description: str,
        guild_id: int | str,
        voting_end: datetime,
        proposer_id: Optional[str] = None,
        status: VotingStatus = VotingStatus.VOTING,
        message_id: Optional[str] = None,
        voting_start: Optional[datetime] = None,
        required_percentage: float = 0.5,
    ) -> Dict[str, Any]:
        """Create a new voting"""
        council_id = f"{guild_id}_c"

        data: Dict[str, Any] = {
            "type": voting_type.value,
            "status": status.value,
            "title": title,
            "description": description,
            "council_id": council_id,
            "voting_end": voting_end.isoformat(),
            "required_percentage": required_percentage,
            "result_announced": False,
        }

        if proposer_id:
            data["proposer_id"] = proposer_id
        if message_id:
            data["message_id"] = str(message_id)
        if voting_start:
            data["voting_start"] = voting_start.isoformat()

        doc_id = message_id if message_id else ID.unique()

        row = self.tables.create_row(
            database_id=self.db_id,
            table_id="votings",
            row_id=str(doc_id),
            data=data,
        )
        return row_to_doc(row)

    async def get_voting(self, voting_id: str) -> Optional[Dict[str, Any]]:
        """Get voting by ID"""
        try:
            row = self.tables.get_row(
                database_id=self.db_id,
                table_id="votings",
                row_id=voting_id,
            )
            return row_to_doc(row)
        except AppwriteException:
            return None

    async def update_voting(self, voting_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update voting data"""
        row = self.tables.update_row(
            database_id=self.db_id,
            table_id="votings",
            row_id=voting_id,
            data=data,
        )
        return row_to_doc(row)

    async def list_active_votings(self, guild_id: int | str) -> List[Dict[str, Any]]:
        """List all active votings for a guild"""
        council_id = f"{guild_id}_c"
        result = self.tables.list_rows(
            database_id=self.db_id,
            table_id="votings",
            queries=[
                Query.equal("council_id", council_id),
                Query.equal("status", VotingStatus.VOTING.value),
            ],
        )
        return wrap_list_rows(result)["documents"]

    # ============================================
    # Vote Operations
    # ============================================

    async def cast_vote(
        self,
        voting_id: str,
        stance: bool,
        councillor_id: Optional[str] = None,
        discord_id: Optional[int | str] = None,
        candidate_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Cast a vote"""
        data: Dict[str, Any] = {
            "voting_id": voting_id,
            "stance": stance,
            "voted_at": datetime.now(timezone.utc).isoformat(),
        }

        if councillor_id:
            data["councillor_id"] = councillor_id
        if discord_id is not None:
            data["discord_id"] = str(discord_id)
        if candidate_id:
            data["candidate_id"] = candidate_id

        row = self.tables.create_row(
            database_id=self.db_id,
            table_id="votes",
            row_id=ID.unique(),
            data=data,
        )
        return row_to_doc(row)

    async def get_votes_for_voting(self, voting_id: str) -> List[Dict[str, Any]]:
        """Get all votes for a voting"""
        result = self.tables.list_rows(
            database_id=self.db_id,
            table_id="votes",
            queries=[Query.equal("voting_id", voting_id)],
        )
        return wrap_list_rows(result)["documents"]

    async def has_voted(
        self,
        voting_id: str,
        councillor_id: Optional[str] = None,
        discord_id: Optional[int | str] = None,
    ) -> bool:
        """Check if a user has already voted"""
        queries = [Query.equal("voting_id", voting_id)]

        if councillor_id:
            queries.append(Query.equal("councillor_id", councillor_id))
        elif discord_id is not None:
            queries.append(Query.equal("discord_id", str(discord_id)))
        else:
            return False

        result = self.tables.list_rows(
            database_id=self.db_id,
            table_id="votes",
            queries=queries,
        )
        return wrap_list_rows(result)["total"] > 0

    # ============================================
    # Election Operations
    # ============================================

    async def register_candidate(
        self,
        voting_id: str,
        discord_id: int | str,
        name: str,
    ) -> Dict[str, Any]:
        """Register a candidate for an election"""
        row = self.tables.create_row(
            database_id=self.db_id,
            table_id="election_candidates",
            row_id=ID.unique(),
            data={
                "voting_id": voting_id,
                "discord_id": str(discord_id),
                "name": name,
                "registered_at": datetime.now(timezone.utc).isoformat(),
                "vote_count": 0,
                "elected": False,
            },
        )
        return row_to_doc(row)

    async def register_voter(
        self,
        voting_id: str,
        discord_id: int | str,
        name: str,
    ) -> Dict[str, Any]:
        """Register a voter for an election"""
        row = self.tables.create_row(
            database_id=self.db_id,
            table_id="registered_voters",
            row_id=ID.unique(),
            data={
                "voting_id": voting_id,
                "discord_id": str(discord_id),
                "name": name,
                "registered_at": datetime.now(timezone.utc).isoformat(),
                "has_voted": False,
            },
        )
        return row_to_doc(row)

    async def get_candidates(self, voting_id: str) -> List[Dict[str, Any]]:
        """Get all candidates for an election"""
        result = self.tables.list_rows(
            database_id=self.db_id,
            table_id="election_candidates",
            queries=[Query.equal("voting_id", voting_id)],
        )
        return wrap_list_rows(result)["documents"]

    async def get_registered_voters(self, voting_id: str) -> List[Dict[str, Any]]:
        """Get all registered voters for an election"""
        result = self.tables.list_rows(
            database_id=self.db_id,
            table_id="registered_voters",
            queries=[Query.equal("voting_id", voting_id)],
        )
        return wrap_list_rows(result)["documents"]

    # ============================================
    # Logging Operations
    # ============================================

    async def log(
        self,
        guild_id: int | str,
        log_type: LogType,
        action: str,
        discord_id: Optional[int | str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: LogSeverity = LogSeverity.INFO,
    ) -> Optional[Dict[str, Any]]:
        """Create a log entry"""
        try:
            data: Dict[str, Any] = {
                "guild_id": str(guild_id),
                "log_type": log_type.value,
                "action": action,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "severity": severity.value,
            }

            if discord_id:
                data["discord_id"] = str(discord_id)
            if details:
                data["details"] = json.dumps(details)

            row = self.tables.create_row(
                database_id=self.db_id,
                table_id="logs",
                row_id=ID.unique(),
                data=data,
            )
            return row_to_doc(row)
        except AppwriteException:
            return None
