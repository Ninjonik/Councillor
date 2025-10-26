# Appwrite Database Setup Guide

This guide will help you set up the Appwrite database structure for the Councillor Discord Bot.

## Database Structure for Appwrite 1.7.4

### Database Name: `councillor`

---

## Collections

### 1. **guilds**
Stores Discord server/guild information and configuration.

**Collection ID**: `guilds`

**Attributes**:
- `guild_id` (string, 36, required) - Discord guild ID
- `name` (string, 256, required) - Guild name
- `description` (string, 1024) - Guild description
- `enabled` (boolean, required, default: true) - Whether the bot is enabled for this guild
- `logging_enabled` (boolean, required, default: true) - Whether to log requests
- `voting_channel_id` (string, 36) - Channel ID for voting posts
- `announcement_channel_id` (string, 36) - Channel ID for announcements
- `councillor_role_id` (string, 36) - Role ID for councillors
- `chancellor_role_id` (string, 36) - Role ID for chancellor
- `minister_role_id` (string, 36) - Role ID for ministers
- `president_role_id` (string, 36) - Role ID for president
- `vice_president_role_id` (string, 36) - Role ID for vice president
- `judiciary_role_id` (string, 36) - Role ID for judiciary
- `citizen_role_id` (string, 36) - Role ID required to participate
- `days_requirement` (integer, required, default: 180) - Days required to join council
- `max_councillors` (integer, required, default: 9) - Maximum number of councillors

**Indexes**:
- `guild_id` (unique, key)

---

### 2. **councils**
Represents a council for each guild.

**Collection ID**: `councils`

**Attributes**:
- `council_id` (string, 50, required) - Format: `{guild_id}_c`
- `guild_id` (string, 36, required) - Related guild ID
- `current_chancellor_id` (string, 36) - Current chancellor's Discord ID
- `election_in_progress` (boolean, required, default: false)

**Indexes**:
- `council_id` (unique, key)
- `guild_id` (key)

**Relationships**:
- `guild` → guilds (many-to-one)

---

### 3. **councillors**
Individual councillor records.

**Collection ID**: `councillors`

**Attributes**:
- `discord_id` (string, 36, required) - Discord user ID
- `name` (string, 256, required) - Discord username
- `council_id` (string, 50, required) - Related council ID
- `joined_at` (datetime, required) - When they became a councillor
- `active` (boolean, required, default: true) - Whether currently active
- `is_chancellor` (boolean, required, default: false) - Whether current chancellor
- `ministry_ids` (string[], 100) - Array of ministry IDs they belong to

**Indexes**:
- `discord_id` (key)
- `council_id` (key)
- `discord_id_council_id` (unique, key: discord_id + council_id)

**Relationships**:
- `council` → councils (many-to-one)

---

### 4. **ministries**
Government ministries managed by the chancellor.

**Collection ID**: `ministries`

**Attributes**:
- `name` (string, 256, required) - Ministry name
- `description` (string, 1024) - Ministry description
- `council_id` (string, 50, required) - Related council ID
- `minister_discord_id` (string, 36) - Minister in charge
- `role_ids` (string[], 100) - Discord role IDs associated with ministry
- `created_by` (string, 36) - Discord ID of creator (chancellor)
- `created_at` (datetime, required)
- `active` (boolean, required, default: true)

**Indexes**:
- `council_id` (key)

**Relationships**:
- `council` → councils (many-to-one)

---

### 5. **votings**
All voting records (proposals, elections, etc.).

**Collection ID**: `votings`

**Attributes**:
- `type` (enum, required) - Values: `legislation`, `amendment`, `impeachment`, `confidence_vote`, `decree`, `other`, `election`, `chancellor_election`
- `status` (enum, required) - Values: `pending`, `voting`, `passed`, `failed`, `cancelled`
- `title` (string, 512, required)
- `description` (string, 4096)
- `council_id` (string, 50, required)
- `proposer_id` (string, 36) - Councillor document ID
- `message_id` (string, 36) - Discord message ID
- `voting_start` (datetime)
- `voting_end` (datetime, required)
- `required_percentage` (float, required, default: 0.5) - Percentage needed to pass
- `result_announced` (boolean, required, default: false)

**Indexes**:
- `council_id` (key)
- `status` (key)
- `type` (key)
- `voting_end` (key)

**Relationships**:
- `council` → councils (many-to-one)
- `proposer` → councillors (many-to-one, optional)

---

### 6. **votes**
Individual votes cast on votings.

**Collection ID**: `votes`

**Attributes**:
- `voting_id` (string, 36, required) - Related voting document ID
- `councillor_id` (string, 36, required) - Councillor document ID
- `discord_id` (string, 36, required) - Discord user ID (for elections)
- `stance` (boolean, required) - true = for/yes, false = against/no
- `candidate_id` (string, 36) - For elections: candidate they voted for
- `voted_at` (datetime, required)

**Indexes**:
- `voting_id` (key)
- `councillor_id` (key)
- `voting_id_councillor_id` (unique, key: voting_id + councillor_id)
- `voting_id_discord_id` (unique, key: voting_id + discord_id)

**Relationships**:
- `voting` → votings (many-to-one)
- `councillor` → councillors (many-to-one, optional)

---

### 7. **election_candidates**
Candidates running in elections.

**Collection ID**: `election_candidates`

**Attributes**:
- `voting_id` (string, 36, required) - Related voting/election ID
- `discord_id` (string, 36, required) - Discord user ID
- `name` (string, 256, required) - Discord username
- `registered_at` (datetime, required)
- `vote_count` (integer, required, default: 0) - Number of votes received
- `elected` (boolean, required, default: false)

**Indexes**:
- `voting_id` (key)
- `voting_id_discord_id` (unique, key: voting_id + discord_id)

**Relationships**:
- `voting` → votings (many-to-one)

---

### 8. **registered_voters**
Users registered to vote in elections.

**Collection ID**: `registered_voters`

**Attributes**:
- `voting_id` (string, 36, required) - Related voting/election ID
- `discord_id` (string, 36, required) - Discord user ID
- `name` (string, 256, required) - Discord username
- `registered_at` (datetime, required)
- `has_voted` (boolean, required, default: false)

**Indexes**:
- `voting_id` (key)
- `voting_id_discord_id` (unique, key: voting_id + discord_id)

**Relationships**:
- `voting` → votings (many-to-one)

---

### 9. **settings**
Bot configuration settings (replaces hardcoded config values).

**Collection ID**: `settings`

**Attributes**:
- `key` (string, 256, required) - Setting key
- `value` (string, 4096, required) - Setting value (JSON serialized if needed)
- `type` (enum, required) - Values: `string`, `integer`, `boolean`, `json`, `array`
- `description` (string, 512) - What this setting does
- `guild_id` (string, 36) - Guild-specific setting (null = global)
- `editable_by` (enum, required, default: admin) - Values: `admin`, `chancellor`, `president`

**Indexes**:
- `key` (key)
- `guild_id` (key)
- `key_guild_id` (unique, key: key + guild_id)

---

### 10. **logs**
Activity and error logs.

**Collection ID**: `logs`

**Attributes**:
- `guild_id` (string, 36, required)
- `log_type` (enum, required) - Values: `command`, `vote`, `election`, `error`, `admin`, `chancellor_action`
- `action` (string, 256, required) - Action performed
- `discord_id` (string, 36) - User who performed action
- `details` (string, 4096) - JSON serialized details
- `timestamp` (datetime, required)
- `severity` (enum, required, default: info) - Values: `debug`, `info`, `warning`, `error`, `critical`

**Indexes**:
- `guild_id` (key)
- `log_type` (key)
- `timestamp` (key)
- `severity` (key)

**Relationships**:
- `guild` → guilds (many-to-one)

---

## Setup Instructions

### Step 1: Create Database
1. Log into your Appwrite Console
2. Create a new database named `councillor`

### Step 2: Create Collections
For each collection listed above:
1. Click "Add Collection"
2. Set the Collection ID as specified
3. Set permissions appropriately (see Permissions section below)

### Step 3: Add Attributes
For each collection, add the attributes as specified with their types and constraints.

### Step 4: Create Indexes
Add the indexes as specified for each collection to improve query performance.

### Step 5: Set Up Relationships
Configure the relationships between collections as specified.

---

## Permissions

### Recommended Permission Structure:

**Read Permissions**:
- All collections: `any` (public read)

**Write Permissions**:
- All collections: None (only server-side with API key)

This ensures only your bot (with API key) can modify data, while allowing public read access for potential future features.

---

## Environment Variables

Update your `config.py` with:

```python
APPWRITE_ENDPOINT = 'https://cloud.appwrite.io/v1'  # or your self-hosted URL
APPWRITE_PROJECT = 'your-project-id'
APPWRITE_KEY = 'your-api-key'
APPWRITE_DB_NAME = 'councillor'
BOT_TOKEN = 'your-discord-bot-token'
DEBUG_MODE = False
ADMIN_USER_ID = '231105080961531905'  # Your Discord user ID
```

---

## Testing

After setup, use the provided `setup_database.py` script to verify your database structure is correct.

---

## Notes

- All Discord IDs are stored as strings
- Dates are stored in ISO 8601 format with timezone
- Enums provide type safety and consistency
- Relationships ensure referential integrity
- Indexes improve query performance significantly

