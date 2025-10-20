# Quick Start Guide

This guide will get your Councillor bot up and running in 15 minutes.

## Prerequisites

✅ Python 3.10 or higher installed
✅ An Appwrite account (Cloud or Self-hosted)
✅ A Discord Bot Token

## Step-by-Step Setup

### 1. Install Dependencies (2 minutes)

```bash
cd /path/to/Councillor
pip install -r requirements.txt
```

### 2. Create Appwrite Database (5 minutes)

1. Log into your Appwrite Console
2. Create a new database named `councillor`
3. Follow `APPWRITE_SETUP.md` to create all 10 collections
4. Set permissions: Read = `any`, Write = `none` (API key only)

**Quick Collection List:**
- guilds
- councils
- councillors
- ministries
- votings
- votes
- election_candidates
- registered_voters
- settings
- logs

### 3. Configure the Bot (2 minutes)

```bash
cp config.example.py config.py
```

Edit `config.py`:

```python
APPWRITE_ENDPOINT = 'https://cloud.appwrite.io/v1'
APPWRITE_PROJECT = 'your-project-id-here'
APPWRITE_KEY = 'your-api-key-here'
APPWRITE_DB_NAME = 'councillor'
BOT_TOKEN = 'your-discord-bot-token-here'
ADMIN_USER_ID = 'your-discord-user-id'
DEBUG_MODE = False
```

**Getting your values:**
- **Project ID**: Appwrite Console → Settings → Project ID
- **API Key**: Appwrite Console → Overview → API Keys → Create API Key (with Database permissions)
- **Bot Token**: Discord Developer Portal → Your Application → Bot → Token
- **Your User ID**: Discord → User Settings → Advanced → Enable Developer Mode → Right-click your username → Copy ID

### 4. Run the Bot (1 minute)

```bash
python main.py
```

You should see:
```
[INFO] Starting Councillor Bot...
[INFO] Loading cogs...
[SUCCESS] Loaded cogs.admin
[SUCCESS] Loaded cogs.chancellor
...
[SUCCESS] Logged in as YourBotName
[SUCCESS] Synced X commands
```

### 5. Initial Discord Setup (5 minutes)

In your Discord server:

1. **Initialize the bot:**
   ```
   /setup
   ```

2. **Set the Councillor role:**
   ```
   /set_role role_type:Councillor role:@Councillor
   ```

3. **Set voting channel:**
   ```
   /set_channel channel_type:Voting Channel channel:#council-voting
   ```

4. **Set requirements:**
   ```
   /set_requirement days:180 max_councillors:9
   ```

5. **View configuration:**
   ```
   /config action:View Configuration
   ```

## Quick Test

Test that everything works:

1. **Check council info:** `/council`
2. **View help:** `/help`
3. **Check server info:** `/info`

## Common Issues

### "This server is not set up yet"
- Run `/setup` first as admin

### "No voting channel configured"
- Run `/set_channel channel_type:Voting Channel channel:#your-channel`

### Database errors
- Verify all collections are created in Appwrite
- Check your API key has database permissions
- Ensure collection IDs match exactly (case-sensitive)

### Commands not showing up
- Wait a few minutes for Discord to sync
- Try kicking and re-inviting the bot
- Check bot has `applications.commands` scope

## Next Steps

Once the bot is running:

1. **Configure all roles** with `/set_role`
2. **Set announcement channel** with `/set_channel`
3. **Announce an election** with `/announce_election`
4. **Let users register** and vote
5. **Start using proposals** with `/propose`

## Need Help?

- Check the full `README.md` for detailed documentation
- Review `APPWRITE_SETUP.md` for database schema details
- Check bot console logs for error details
- Review Appwrite logs in the Console

---

**You're ready to bring democracy to Discord! 🏛️**

