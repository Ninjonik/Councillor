"""
Enums for the Councillor Discord Bot
Provides type safety and consistency across the application
"""
from enum import Enum


class VotingType(Enum):
    """Types of votings that can be created"""
    LEGISLATION = "legislation"
    AMENDMENT = "amendment"
    IMPEACHMENT = "impeachment"
    CONFIDENCE_VOTE = "confidence_vote"
    DECREE = "decree"
    OTHER = "other"
    ELECTION = "election"
    CHANCELLOR_ELECTION = "chancellor_election"


class VotingStatus(Enum):
    """Status of a voting"""
    PENDING = "pending"
    VOTING = "voting"
    PASSED = "passed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RoleType(Enum):
    """Types of roles in the democracy system"""
    COUNCILLOR = "councillor"
    CHANCELLOR = "chancellor"
    MINISTER = "minister"
    JUDICIARY = "judiciary"
    PRESIDENT = "president"
    VICE_PRESIDENT = "vice_president"


class LogType(Enum):
    """Types of logs"""
    COMMAND = "command"
    VOTE = "vote"
    ELECTION = "election"
    ERROR = "error"
    ADMIN = "admin"
    CHANCELLOR_ACTION = "chancellor_action"


class LogSeverity(Enum):
    """Log severity levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class SettingType(Enum):
    """Types of settings"""
    STRING = "string"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    JSON = "json"
    ARRAY = "array"


class EditableBy(Enum):
    """Who can edit a setting"""
    ADMIN = "admin"
    CHANCELLOR = "chancellor"
    PRESIDENT = "president"


# Voting type configurations
VOTING_TYPE_CONFIG = {
    VotingType.LEGISLATION: {
        "text": "Legislation",
        "color": 0x4169E1,
        "emoji": "⚖️",
        "voting_days": 1,
        "required_percentage": 0.5,
        "description": "Regular legislative proposals"
    },
    VotingType.AMENDMENT: {
        "text": "Amendment",
        "color": 0x8A2BE2,
        "emoji": "🔵",
        "voting_days": 3,
        "required_percentage": 0.66,
        "description": "Constitutional amendments requiring supermajority"
    },
    VotingType.IMPEACHMENT: {
        "text": "Impeachment",
        "color": 0xFF6347,
        "emoji": "📜",
        "voting_days": 3,
        "required_percentage": 0.66,
        "description": "Removal of officials from office"
    },
    VotingType.CONFIDENCE_VOTE: {
        "text": "Confidence Vote",
        "color": 0xFF4500,
        "emoji": "⚠️",
        "voting_days": 3,
        "required_percentage": 0.66,
        "description": "Vote of confidence in leadership"
    },
    VotingType.DECREE: {
        "text": "Decree",
        "color": 0xFFA500,
        "emoji": "🛑",
        "voting_days": 1,
        "required_percentage": 0.5,
        "description": "Executive orders and decrees"
    },
    VotingType.OTHER: {
        "text": "Other",
        "color": 0x20B2AA,
        "emoji": "🗳️",
        "voting_days": 3,
        "required_percentage": 0.5,
        "description": "Miscellaneous proposals"
    },
    VotingType.ELECTION: {
        "text": "Council Election",
        "color": 0x00B0F4,
        "emoji": "🗳️",
        "voting_days": 3,
        "required_percentage": 0.0,  # Elections don't use percentage
        "description": "Elections for council members"
    },
    VotingType.CHANCELLOR_ELECTION: {
        "text": "Chancellor Election",
        "color": 0xFFD700,
        "emoji": "👑",
        "voting_days": 2,
        "required_percentage": 0.0,  # Elections don't use percentage
        "description": "Elections for chancellor (councillors only)"
    },
}

