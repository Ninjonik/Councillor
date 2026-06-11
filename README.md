# DISCONTINUED
# Councillor Discord Bot

A comprehensive Discord bot for managing democratic processes in Discord communities. Built with discord.py 2.6.4 and Appwrite 1.7.4.

## 🌟 Features

### Democracy System
- **Council Elections** - Democratic elections for council members
- **Chancellor Elections** - Councillors elect a Chancellor from among themselves
- **Voting & Proposals** - Create and vote on legislation, amendments, and more
- **Ministry Management** - Chancellor can create and manage government ministries
- **Role-based Permissions** - Granular permission system for different roles

### Modern Architecture
- ✅ **Database-driven Configuration** - All settings stored in Appwrite, no hardcoded values
- ✅ **Enum-based Type Safety** - Strong typing with Python enums
- ✅ **Relationship Support** - Proper database relationships and referential integrity
- ✅ **Better Error Handling** - Comprehensive error messages and logging
- ✅ **Improved UX/UI** - Consistent Discord markdown formatting and modern embeds
- ✅ **Permission Checks** - Users only see commands they can actually use
- ✅ **Activity Logging** - Comprehensive logging of all democratic actions

## 📋 Requirements

- Python 3.10+
- Discord Bot Token
- Appwrite 1.7.4 instance (Cloud or Self-hosted)

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd Councillor
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Set Up Appwrite Database

Follow the detailed instructions in `APPWRITE_SETUP.md` to create all necessary collections and configure your Appwrite database.

### 4. Configure the Bot

Copy `config.example.py` to `config.py`:

```bash
cp config.example.py config.py
```

Edit `config.py` with your credentials:

```python
# Appwrite Configuration
APPWRITE_ENDPOINT = 'https://cloud.appwrite.io/v1'  # or your self-hosted URL
APPWRITE_PROJECT = 'your-project-id'
APPWRITE_KEY = 'your-api-key'
APPWRITE_DB_NAME = 'councillor'

# Discord Configuration
BOT_TOKEN = 'your-discord-bot-token'

# Admin Configuration
ADMIN_USER_ID = 'your-discord-user-id'

# Debug Mode
DEBUG_MODE = False
```

### 5. Run the Bot

```bash
python main.py
```

## 📖 Usage

### Initial Setup

1. **Invite the bot** to your Discord server with appropriate permissions
2. **Run `/setup`** (Admin only) to initialize the bot for your server
3. **Configure roles** with `/set_role` for each democratic role
4. **Configure channels** with `/set_channel` for voting and announcements
5. **Set requirements** with `/set_requirement` for participation eligibility

### Command Categories

#### 📋 General Commands (Everyone)
- `/council` - Learn about the Grand Council and check eligibility
- `/info` - View current council members and information
- `/voting_info` - See active votings and proposals
- `/help` - Display help information

#### ⚖️ Councillor Commands
- `/propose` - Create a new proposal for council voting
  - Legislation
  - Amendments
  - Impeachment
  - Confidence Votes
  - Decrees
  - Other proposals

#### 👑 Chancellor Commands
- `/create_ministry` - Create a new government ministry
- `/assign_minister` - Assign a minister to a ministry
- `/list_ministries` - View all ministries
- `/announce` - Make an official announcement
- `/appoint_role` - Associate a Discord role with a ministry
- `/remove_ministry` - Remove/deactivate a ministry

#### 🔧 Admin Commands
- `/setup` - Initial bot setup for the server
- `/config` - View current configuration
- `/set_role` - Configure role assignments
- `/set_channel` - Configure channels for bot operations
- `/set_requirement` - Set participation requirements (days, max councillors)
- `/toggle_bot` - Enable or disable the bot
- `/announce_election` - Announce and manage elections

## 🏗️ Project Structure

```
Councillor/
├── main.py                 # Main bot entry point
├── config.py              # Configuration (create from config.example.py)
├── config.example.py      # Example configuration
├── requirements.txt       # Python dependencies
├── APPWRITE_SETUP.md     # Database setup guide
├── README.md             # This file
├── utils/                # Utility modules
│   ├── __init__.py
│   ├── database.py       # Database helper functions
│   ├── enums.py          # Enumerations for type safety
│   ├── errors.py         # Error handling
│   ├── formatting.py     # Discord formatting utilities
│   ├── helpers.py        # General helper functions
│   └── permissions.py    # Permission checking
└── cogs/                 # Command modules
    ├── admin.py          # Admin commands
    ├── chancellor.py     # Chancellor commands
    ├── council.py        # Council information
    ├── elections.py      # Election management
    ├── info.py           # Information display
    └── propose.py        # Proposal creation and voting
```

## 🎯 Key Concepts

### Roles

The bot supports the following democratic roles:

- **Councillor** - Elected members who can vote on proposals
- **Chancellor** - Head of council with special powers
- **Minister** - Heads of government ministries
- **President/Vice President** - Can manage elections
- **Judiciary** - For future judicial features
- **Citizen** - Required role for participation (optional)

### Voting Types

- **Legislation** (50% required, 1 day voting)
- **Amendment** (66% required, 3 days voting)
- **Impeachment** (66% required, 3 days voting)
- **Confidence Vote** (66% required, 3 days voting)
- **Decree** (50% required, 1 day voting)
- **Other** (50% required, 3 days voting)

### Elections

1. **Announcement Phase** - President announces election, citizens register
2. **Voting Phase** - Registered voters vote for candidates
3. **Results** - Top candidates become councillors
4. **Chancellor Election** - Councillors elect a Chancellor

## 🔒 Security & Permissions

- **Admin Commands** - Only accessible to configured admin user
- **Chancellor Commands** - Only for elected Chancellor
- **Councillor Commands** - Only for elected Councillors
- **Automatic Permission Checks** - Users only see commands they can use
- **Database-level Security** - All write operations server-side only

## 📊 Logging & Monitoring

All significant actions are logged:
- Command usage
- Vote casting
- Elections
- Chancellor actions
- Errors

Logs can be viewed in the Appwrite console for auditing and debugging.

## 🎨 Design Principles

This bot follows the **KISS (Keep It Simple, Stupid)** principle:

- **Modular Code** - Each feature in its own module
- **Consistent Formatting** - Uniform Discord markdown and embeds
- **Clear Error Messages** - Users always know what went wrong
- **Type Safety** - Enums and type hints throughout
- **Database-driven** - No hardcoded configuration

## 🔧 Development

### Adding a New Command

1. Choose the appropriate cog in `cogs/`
2. Use the `@app_commands.command()` decorator
3. Add permission checks using utilities from `utils/permissions.py`
4. Use formatting utilities from `utils/formatting.py`
5. Handle errors with `handle_interaction_error()`
6. Log important actions with `db_helper.log()`

### Adding a New Voting Type

1. Add to `VotingType` enum in `utils/enums.py`
2. Add configuration to `VOTING_TYPE_CONFIG`
3. Add choice to `/propose` command in `cogs/propose.py`

## 🤝 Contributing

Contributions are welcome! Please ensure:
- Code follows existing style and patterns
- New features include error handling
- Database changes are documented
- Commands use permission checks appropriately

## 📝 License

See LICENSE file for details.

## 🆘 Support

For issues or questions:
1. Check the `APPWRITE_SETUP.md` guide
2. Review error logs in Appwrite console
3. Check bot console output for error details

## ✨ Features Coming Soon

- Judicial system for dispute resolution
- Vote delegation
- Proposal templates
- Advanced analytics dashboard
- Multi-language support

---

**Built with ❤️ for democratic Discord communities**
