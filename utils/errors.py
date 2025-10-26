"""
Error handling utilities for the Councillor Bot
"""
import discord
from discord.ext import commands
from discord import app_commands
import traceback
from typing import Union


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
        await ctx.send("❌ You must be a councillor to use this command.", ephemeral=True)

    elif isinstance(error, NotChancellorError):
        await ctx.send("❌ You must be the chancellor to use this command.", ephemeral=True)

    elif isinstance(error, NotAdminError):
        await ctx.send("❌ You must be an admin to use this command.", ephemeral=True)

    elif isinstance(error, PermissionError):
        await ctx.send("❌ You lack the required permissions to use this command.", ephemeral=True)

    elif isinstance(error, NotEligibleError):
        await ctx.send("❌ You are not eligible to perform this action.", ephemeral=True)

    elif isinstance(error, NotFoundError):
        await ctx.send("❌ The requested resource was not found.", ephemeral=True)

    elif isinstance(error, AlreadyExistsError):
        await ctx.send("❌ The resource you are trying to create already exists.", ephemeral=True)

    elif isinstance(error, InvalidInputError):
        await ctx.send("❌ The provided input is invalid.", ephemeral=True)

    elif isinstance(error, GuildNotSetupError):
        await ctx.send("❌ This server is not properly set up. Please contact an administrator.", ephemeral=True)

    elif isinstance(error, VotingNotFoundError):
        await ctx.send("❌ Voting not found.", ephemeral=True)

    elif isinstance(error, AlreadyVotedError):
        await ctx.send("❌ You have already voted.", ephemeral=True)

    elif isinstance(error, ElectionInProgressError):
        await ctx.send("❌ An election is already in progress.", ephemeral=True)

    # Handle built-in command errors
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing required argument: `{error.param.name}`", ephemeral=True)

    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Invalid argument: {error}", ephemeral=True)

    elif isinstance(error, commands.MissingPermissions):
        perms = ", ".join(error.missing_permissions)
        await ctx.send(f"❌ You are missing required permissions: {perms}", ephemeral=True)

    elif isinstance(error, commands.BotMissingPermissions):
        perms = ", ".join(error.missing_permissions)
        await ctx.send(f"❌ I am missing required permissions: {perms}", ephemeral=True)

    elif isinstance(error, commands.CommandNotFound):
        # Silently ignore command not found errors
        pass

    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"❌ This command is on cooldown. Try again in {error.retry_after:.1f} seconds.", ephemeral=True)

    elif isinstance(error, commands.NoPrivateMessage):
        await ctx.send("❌ This command cannot be used in private messages.", ephemeral=True)

    # Handle any other errors
    else:
        error_msg = f"❌ An error occurred: {str(error)}"
        await ctx.send(error_msg, ephemeral=True)

        # Log the full traceback
        print(f"Error in command {ctx.command}:")
        traceback.print_exception(type(error), error, error.__traceback__)


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
        await interaction.response.send_message("❌ You must be a councillor to use this command.", ephemeral=True)

    elif isinstance(error, NotChancellorError):
        await interaction.response.send_message("❌ You must be the chancellor to use this command.", ephemeral=True)

    elif isinstance(error, NotAdminError):
        await interaction.response.send_message("❌ You must be an admin to use this command.", ephemeral=True)

    elif isinstance(error, PermissionError):
        await interaction.response.send_message("❌ You lack the required permissions to use this command.", ephemeral=True)

    elif isinstance(error, NotEligibleError):
        await interaction.response.send_message("❌ You are not eligible to perform this action.", ephemeral=True)

    elif isinstance(error, NotFoundError):
        await interaction.response.send_message("❌ The requested resource was not found.", ephemeral=True)

    elif isinstance(error, AlreadyExistsError):
        await interaction.response.send_message("❌ The resource you are trying to create already exists.", ephemeral=True)

    elif isinstance(error, InvalidInputError):
        await interaction.response.send_message(f"❌ The provided input is invalid. {error}", ephemeral=True)

    elif isinstance(error, GuildNotSetupError):
        await interaction.response.send_message("❌ This server is not properly set up. Please contact an administrator.", ephemeral=True)

    elif isinstance(error, VotingNotFoundError):
        await interaction.response.send_message("❌ Voting not found.", ephemeral=True)

    elif isinstance(error, AlreadyVotedError):
        await interaction.response.send_message("❌ You have already voted.", ephemeral=True)

    elif isinstance(error, ElectionInProgressError):
        await interaction.response.send_message("❌ An election is already in progress.", ephemeral=True)

    # Handle built-in app command errors
    elif isinstance(error, app_commands.MissingPermissions):
        perms = ", ".join(error.missing_permissions)
        await interaction.response.send_message(f"❌ You are missing required permissions: {perms}", ephemeral=True)

    elif isinstance(error, app_commands.BotMissingPermissions):
        perms = ", ".join(error.missing_permissions)
        await interaction.response.send_message(f"❌ I am missing required permissions: {perms}", ephemeral=True)

    elif isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(f"❌ This command is on cooldown. Try again in {error.retry_after:.1f} seconds.", ephemeral=True)

    # Handle any other errors
    else:
        error_msg = f"❌ An error occurred: {str(error)}"

        # Check if we already responded
        if interaction.response.is_done():
            await interaction.followup.send(error_msg, ephemeral=True)
        else:
            await interaction.response.send_message(error_msg, ephemeral=True)

        # Log the full traceback
        print(f"Error in slash command {interaction.command.name if interaction.command else 'unknown'}:")
        traceback.print_exception(type(error), error, error.__traceback__)


# Alias handle_app_command_error as handle_interaction_error
handle_interaction_error = handle_app_command_error
