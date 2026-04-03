"""
Error handling utilities for the Councillor Bot
"""
import discord
from discord.ext import commands
from discord import app_commands
import traceback


class CouncillorError(Exception):
    """Base exception for Councillor Bot errors"""
    pass


class NotCouncillorError(CouncillorError):
    """Raised when a user is not a councillor"""
    pass


class NotChancellorError(CouncillorError):
    """Raised when a user is not the chancellor"""
    pass


class NotAdminError(CouncillorError):
    """Raised when a user is not an admin"""
    pass


class PermissionError(CouncillorError):
    """Raised when a user lacks required permissions"""
    pass


class NotEligibleError(CouncillorError):
    """Raised when a user is not eligible for an action"""
    pass


class NotFoundError(CouncillorError):
    """Raised when a resource is not found"""
    pass


class AlreadyExistsError(CouncillorError):
    """Raised when a resource already exists"""
    pass


class InvalidInputError(CouncillorError):
    """Raised when user input is invalid"""
    pass


class GuildNotSetupError(CouncillorError):
    """Raised when a guild is not properly set up"""
    pass


class VotingNotFoundError(CouncillorError):
    """Raised when a voting is not found"""
    pass


class AlreadyVotedError(CouncillorError):
    """Raised when a user tries to vote twice"""
    pass


class ElectionInProgressError(CouncillorError):
    """Raised when trying to start an election while one is in progress"""
    pass


async def handle_command_error(ctx: commands.Context, error: Exception):
    """
    Global error handler for text commands

    Args:
        ctx: The command context
        error: The error that occurred
    """
    # Unwrap CommandInvokeError
    if isinstance(error, commands.CommandInvokeError):
        error = error.original

    # Handle custom errors
    if isinstance(error, NotCouncillorError):
        await ctx.send("❌ You must be a councillor to use this command.")

    elif isinstance(error, NotChancellorError):
        await ctx.send("❌ You must be the chancellor to use this command.")

    elif isinstance(error, NotAdminError):
        await ctx.send("❌ You must be an admin to use this command.")

    elif isinstance(error, PermissionError):
        await ctx.send("❌ You lack the required permissions to use this command.")

    elif isinstance(error, NotEligibleError):
        await ctx.send("❌ You are not eligible to perform this action.")

    elif isinstance(error, NotFoundError):
        await ctx.send("❌ The requested resource was not found.")

    elif isinstance(error, AlreadyExistsError):
        await ctx.send("❌ The resource you are trying to create already exists.")

    elif isinstance(error, InvalidInputError):
        await ctx.send("❌ The provided input is invalid.")

    elif isinstance(error, GuildNotSetupError):
        await ctx.send("❌ This server is not properly set up. Please contact an administrator.")

    elif isinstance(error, VotingNotFoundError):
        await ctx.send("❌ Voting not found.")

    elif isinstance(error, AlreadyVotedError):
        await ctx.send("❌ You have already voted.")

    elif isinstance(error, ElectionInProgressError):
        await ctx.send("❌ An election is already in progress.")

    # Handle built-in command errors
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing required argument: `{error.param.name}`")

    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Invalid argument: {error}")

    elif isinstance(error, commands.MissingPermissions):
        perms = ", ".join(error.missing_permissions)
        await ctx.send(f"❌ You are missing required permissions: {perms}")

    elif isinstance(error, commands.BotMissingPermissions):
        perms = ", ".join(error.missing_permissions)
        await ctx.send(f"❌ I am missing required permissions: {perms}")

    elif isinstance(error, commands.CommandNotFound):
        # Silently ignore command not found errors
        pass

    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"❌ This command is on cooldown. Try again in {error.retry_after:.1f} seconds.")

    elif isinstance(error, commands.NoPrivateMessage):
        await ctx.send("❌ This command cannot be used in private messages.")

    # Handle any other errors
    else:
        error_msg = f"❌ An error occurred: {str(error)}"
        await ctx.send(error_msg)

        # Log the full traceback
        print(f"Error in command {ctx.command}:")
        traceback.print_exception(type(error), error, error.__traceback__)


async def _safe_interaction_send(interaction: discord.Interaction, message: str, ephemeral: bool = True):
    """Send an interaction message safely, tolerating expired interactions."""
    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(message, ephemeral=ephemeral)
    except discord.NotFound:
        # Interaction token expired or unknown interaction; avoid noisy secondary exceptions.
        print("Interaction response skipped: token expired or interaction no longer valid.")
    except discord.HTTPException as send_error:
        print(f"Failed to send interaction response: {send_error}")


async def handle_app_command_error(interaction: discord.Interaction, error: Exception):
    """
    Error handler for application (slash) commands

    Args:
        interaction: The interaction that triggered the error
        error: The error that occurred
    """
    # Unwrap CommandInvokeError
    if isinstance(error, app_commands.CommandInvokeError):
        error = error.original

    # Handle custom errors
    if isinstance(error, NotCouncillorError):
        error_msg = "❌ You must be a councillor to use this command."
    elif isinstance(error, NotChancellorError):
        error_msg = "❌ You must be the chancellor to use this command."
    elif isinstance(error, NotAdminError):
        error_msg = "❌ You must be an admin to use this command."
    elif isinstance(error, PermissionError):
        error_msg = "❌ You lack the required permissions to use this command."
    elif isinstance(error, NotEligibleError):
        error_msg = "❌ You are not eligible to perform this action."
    elif isinstance(error, NotFoundError):
        error_msg = "❌ The requested resource was not found."
    elif isinstance(error, AlreadyExistsError):
        error_msg = "❌ The resource you are trying to create already exists."
    elif isinstance(error, InvalidInputError):
        error_msg = "❌ The provided input is invalid."
    elif isinstance(error, GuildNotSetupError):
        error_msg = "❌ This server is not properly set up. Please contact an administrator."
    elif isinstance(error, VotingNotFoundError):
        error_msg = "❌ Voting not found."
    elif isinstance(error, AlreadyVotedError):
        error_msg = "❌ You have already voted."
    elif isinstance(error, ElectionInProgressError):
        error_msg = "❌ An election is already in progress."
    # Handle built-in app command errors
    elif isinstance(error, app_commands.MissingPermissions):
        perms = ", ".join(error.missing_permissions)
        error_msg = f"❌ You are missing required permissions: {perms}"
    elif isinstance(error, app_commands.BotMissingPermissions):
        perms = ", ".join(error.missing_permissions)
        error_msg = f"❌ I am missing required permissions: {perms}"
    elif isinstance(error, app_commands.CommandOnCooldown):
        error_msg = f"❌ This command is on cooldown. Try again in {error.retry_after:.1f} seconds."
    # Handle any other errors
    else:
        error_msg = f"❌ An error occurred: {str(error)}"
        print(f"Error in slash command {interaction.command.name if interaction.command else 'unknown'}:")
        traceback.print_exception(type(error), error, error.__traceback__)

    await _safe_interaction_send(interaction, error_msg, ephemeral=True)


# Alias handle_app_command_error as handle_interaction_error
handle_interaction_error = handle_app_command_error
