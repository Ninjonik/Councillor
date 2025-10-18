# Councillor - Democratic Discord Governance Bot

A streamlined Discord bot for managing democratic elections and government roles with Appwrite backend.

## 🎯 Key Features

- **Electoral System**: MPs must be elected (no self-appointment)
- **Democratic Process**: Community votes on all government positions
- **Role-Based Commands**: Commands visible only to authorized roles
- **Multi-Server Support**: Works on any server with per-server data storage
- **Appwrite Backend**: Scalable data storage

## 📋 Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Copy `.env.example` to `.env` and fill in your credentials:
```bash
cp .env.example .env
```

Edit `.env` with your actual values:
- **DISCORD_TOKEN** - Your Discord bot token from [Discord Developer Portal](https://discord.com/developers/applications)
- **APPWRITE_ENDPOINT** - Your Appwrite endpoint (default: https://cloud.appwrite.io/v1)
- **APPWRITE_PROJECT_ID** - Your Appwrite project ID
- **APPWRITE_API_KEY** - Your Appwrite API key with database permissions
- **APPWRITE_DATABASE_ID** - Your Appwrite database ID

### 3. Run Database Migration
```bash
python migrate.py
```

This creates the necessary collections in Appwrite.

### 4. Start the Bot
```bash
python main.py
```

### 5. Setup Each Discord Server
The bot works on multiple servers! For each server:

1. Use `/setup_roles` to create government roles (Chancellor, MP, Citizen)
2. Use `/sync_commands` to enable all slash commands
3. **Configure Role Permissions** in Discord:
   - Give **Chancellor** role the **"Manage Server"** permission
   - Give **MP** role the **"Manage Messages"** permission
   - **Citizen** role needs no special permissions (default)

Each server has its own independent government, elections, and members stored in Appwrite.

## 🏛️ Government Structure

### Citizen
- Register with `/register`
- Vote in elections
- Can run for MP
- **Public commands** - visible to everyone

### Member of Parliament (MP)
- **Must be elected** via `/run_for_mp`
- Requires minimum votes to win
- Can run for Chancellor
- **MP commands** - visible only to those with "Manage Messages" permission

### Chancellor
- **Must be elected MP first**
- Run via `/run_for_chancellor`
- Full server management powers through bot
- **Chancellor commands** - visible only to those with "Manage Server" permission

## 📜 Commands

### For Everyone (Public)
- `/register` - Register as a citizen
- `/my_status` - Check your government status
- `/government` - View current government members
- `/run_for_mp` - Start MP election campaign
- `/run_for_chancellor` - Start Chancellor election campaign (MPs only)
- `/active_elections` - View active elections
- `/resign` - Resign from position

### For MPs (Requires "Manage Messages" Permission)
- `/propose` - Create a new proposal for voting
- `/view_proposals` - View all active proposals
- `/moderate_message` - Delete a message for moderation
- `/mp_announcement` - Send a parliamentary announcement

### For Chancellor (Requires "Manage Server" Permission)
- `/kick` - Kick a member
- `/ban` - Ban a member
- `/unban` - Unban a user
- `/timeout` - Timeout a member
- `/add_role` - Add role to member
- `/remove_role` - Remove role from member
- `/lock_channel` - Lock a channel
- `/unlock_channel` - Unlock a channel
- `/purge` - Delete multiple messages
- `/announce` - Send official announcement

### For Admins (Requires "Administrator" Permission)
- `/setup_roles` - Create government roles
- `/sync_commands` - Sync slash commands

## 🔐 Permission System

The bot uses Discord's native permission system for command visibility:

1. **Default Permissions**: Commands are tagged with required Discord permissions
   - `administrator` - Admin commands
   - `manage_guild` - Chancellor commands
   - `manage_messages` - MP commands
   - None - Public commands

2. **Role Configuration**: Server admins assign Discord permissions to government roles:
   ```
   Chancellor Role → Manage Server permission
   MP Role → Manage Messages permission
   Citizen Role → No special permissions
   ```

3. **Command Visibility**: Discord automatically shows/hides commands based on user permissions
   - Users only see commands they can use
   - No clutter, better UX
   - Native Discord integration

4. **Runtime Verification**: Bot double-checks government role membership
   - Ensures only elected officials use commands
   - Prevents abuse from permission-only access

## 🗳️ Election Process

1. Citizen runs for MP with `/run_for_mp`
2. Election message posted with voting buttons
3. Citizens vote FOR or AGAINST
4. Election passes with minimum votes (default: 3)
5. Winner automatically receives MP role
6. MPs can run for Chancellor (same process)

## 🛠️ Technical Details

- **Backend**: Appwrite (cloud or self-hosted)
- **Framework**: discord.py 2.3+
- **Architecture**: Cog-based modular design
- **Database**: Appwrite collections for members, elections, votes, proposals
- **Design**: KISS principles - simple and maintainable
- **Permissions**: Native Discord permission system with `@app_commands.default_permissions()`

## 📚 Project Structure

```
Councillor/
├── main.py              # Bot entry point
├── config.py            # Configuration
├── utils.py             # Shared utilities & DB helpers
├── embeds.py            # Embed templates
├── views.py             # Interactive UI components
├── migrate.py           # Database setup
├── cogs/
│   ├── admin.py         # Admin commands
│   ├── elections.py     # Election system
│   ├── executive.py     # Chancellor commands
│   ├── parliament.py    # MP commands
│   └── governance.py    # General governance
└── requirements.txt
```

## 📝 License

See LICENSE file for details.
