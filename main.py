import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import config
from embeds import error_embed
from logger import log
from utils import db

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
bot.db = db  # Attach database client to bot

@bot.event
async def on_ready():
    log.success(f"{bot.user} is online!")
    log.info(f"Connected to {len(bot.guilds)} guild(s)")

    # Load cogs
    cogs = ["cogs.admin", "cogs.elections", "cogs.executive", "cogs.parliament", "cogs.governance"]
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            log.success(f"Loaded {cog}")
        except Exception as e:
            log.error(f"Failed to load {cog}: {e}")

    # Sync commands globally
    try:
        log.info("Syncing slash commands globally...")
        synced = await bot.tree.sync()
        log.success(f"Synced {len(synced)} command(s) globally")
    except Exception as e:
        log.error(f"Failed to sync commands: {e}")

    log.success("Bot is ready!")

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Global error handler for slash commands"""

    # Handle command on cooldown
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(
            embed=error_embed("Cooldown", f"This command is on cooldown. Try again in {error.retry_after:.1f} seconds."),
            ephemeral=True
        )
        return

    # Handle missing permissions
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            embed=error_embed("Missing Permissions", "You don't have permission to use this command."),
            ephemeral=True
        )
        return

    # Handle bot missing permissions
    if isinstance(error, app_commands.BotMissingPermissions):
        await interaction.response.send_message(
            embed=error_embed("Bot Missing Permissions", "I don't have the required permissions to execute this command."),
            ephemeral=True
        )
        return

    # Log unexpected errors
    log.error(f"Command error: {error}")

    if not interaction.response.is_done():
        await interaction.response.send_message(
            embed=error_embed("Error", "An unexpected error occurred. Please try again later."),
            ephemeral=True
        )
    else:
        await interaction.followup.send(
            embed=error_embed("Error", "An unexpected error occurred. Please try again later."),
            ephemeral=True
        )

@bot.event
async def on_guild_join(guild):
    """Send setup instructions when bot joins a server"""
    log.info(f"Joined new guild: {guild.name} (ID: {guild.id})")

    if guild.system_channel:
        embed = discord.Embed(
            title="👋 Thanks for adding me!",
            description="I'm a Grand Council governance bot that manages democratic elections according to the World War Community Constitution.",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="📋 Setup Steps",
            value="1. Create Discord roles: `President`, `Vice President`, `Chancellor`, `Councillor`, `Citizen`\n"
                  "2. Assign President and Vice President roles manually to leadership\n"
                  "3. President/VP can use `/elections` to manage Grand Council elections\n"
                  "4. Citizens can register to vote or run for Council during election announcements",
            inline=False
        )
        embed.set_footer(text="Run /help for more information")
        try:
            await guild.system_channel.send(embed=embed)
        except discord.Forbidden:
            pass

def main():
    """Run the bot"""
    if not config.DISCORD_TOKEN:
        log.error("DISCORD_TOKEN not found in config!")
        return

    if not all([config.APPWRITE_ENDPOINT, config.APPWRITE_PROJECT_ID, config.APPWRITE_API_KEY]):
        log.warning("Appwrite credentials not configured!")

    log.info("Starting bot...")
    bot.run(config.DISCORD_TOKEN)

if __name__ == "__main__":
    main()
