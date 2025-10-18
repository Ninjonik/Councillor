import os
from dotenv import load_dotenv
from logger import log

load_dotenv()

# Discord
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Appwrite
APPWRITE_ENDPOINT = os.getenv("APPWRITE_ENDPOINT", "https://cloud.appwrite.io/v1")
APPWRITE_PROJECT_ID = os.getenv("APPWRITE_PROJECT_ID")
APPWRITE_API_KEY = os.getenv("APPWRITE_API_KEY")
APPWRITE_DATABASE_ID = os.getenv("APPWRITE_DATABASE_ID")
APPWRITE_DB_NAME = APPWRITE_DATABASE_ID  # Alias for compatibility

# Collections (defaults - will be created by migrate.py)
COLLECTION_COUNCILLORS = os.getenv("COLLECTION_COUNCILLORS", "councillors")
COLLECTION_VOTINGS = os.getenv("COLLECTION_VOTINGS", "votings")
COLLECTION_REGISTERED = os.getenv("COLLECTION_REGISTERED", "registered")
COLLECTION_VOTED = os.getenv("COLLECTION_VOTED", "voted")
COLLECTION_PROPOSALS = os.getenv("COLLECTION_PROPOSALS", "proposals")
COLLECTION_GUILDS = os.getenv("COLLECTION_GUILDS", "guilds")
COLLECTION_VOTES = os.getenv("COLLECTION_VOTES", "votes")
COLLECTION_MINISTRIES = os.getenv("COLLECTION_MINISTRIES", "ministries")

# Election settings (these are just constants, not role names)
ELECTION_DURATION = 24 * 3600  # 24 hours in seconds
COUNCILLOR_TERM_MONTHS = 3  # Term length in months
COUNCILLORS_TOTAL = 12  # Total council seats
COUNCILLORS_PER_ELECTION = 4  # New councillors elected each month
MIN_NEW_COUNCILLORS = 4  # Minimum new councillors per election
MAX_CANDIDATES = 9  # Maximum candidates per election
VOTING_AGE_DAYS = 30  # Members must be in server for 30 days to vote

# Voting types configuration (these are labels, not role names)
VOTING_TYPES = {
    "legislation": {
        "name": "Legislation",
        "emoji": "⚖️",
        "voting_days": 1,
        "required_percentage": 0.5,
        "description": "New laws and regulations"
    },
    "decree": {
        "name": "Decree",
        "emoji": "🛑",
        "voting_days": 1,
        "required_percentage": 0.5,
        "description": "Emergency or temporary measures"
    },
    "amendment": {
        "name": "Constitutional Amendment",
        "emoji": "🔵",
        "voting_days": 3,
        "required_percentage": 0.66,
        "description": "Changes to the Constitution"
    },
    "impeachment": {
        "name": "Impeachment",
        "emoji": "📜",
        "voting_days": 3,
        "required_percentage": 0.66,
        "description": "Removal of officials from office"
    },
    "confidence_vote": {
        "name": "Vote of Confidence",
        "emoji": "⚠️",
        "voting_days": 3,
        "required_percentage": 0.5,
        "description": "Confidence in leadership"
    },
    "other": {
        "name": "Other Vote",
        "emoji": "🗳️",
        "voting_days": 3,
        "required_percentage": 0.5,
        "description": "General proposals"
    }
}

# Validate critical configuration
if not DISCORD_TOKEN:
    log.error("DISCORD_TOKEN is required in .env file")
    raise ValueError("❌ DISCORD_TOKEN is required in .env file")

if not all([APPWRITE_PROJECT_ID, APPWRITE_API_KEY, APPWRITE_DATABASE_ID]):
    log.error("Missing Appwrite configuration")
    raise ValueError("❌ APPWRITE_PROJECT_ID, APPWRITE_API_KEY, and APPWRITE_DATABASE_ID are required")
