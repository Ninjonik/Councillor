"""
Permission checking utilities
Determines if users have the required roles and permissions
"""
from typing import Optional
import discord

import config
from utils.enums import RoleType
from utils.database import DatabaseHelper
from utils.errors import NotEligibleError, PermissionError


async def is_admin(user: discord.User | discord.Member) -> bool:
    """Check if user is an admin"""
    return str(user.id) == config.ADMIN_USER_ID


async def is_eligible(
    user: discord.Member,
    guild: discord.Guild,
    role: RoleType,
    db_helper: DatabaseHelper
) -> bool:
    """
    Check if a user is eligible for a specific role

    Args:
        user: Discord member to check
        guild: Discord guild
        role: Role type to check for
        db_helper: Database helper instance

    Returns:
        True if eligible, False otherwise
    """
    # Admin can do everything
    if await is_admin(user):
        return True

    guild_data = await db_helper.get_guild(guild.id)

    if not guild_data:
        return False

    # Map role type to role ID field
    role_field_map = {
        RoleType.COUNCILLOR: 'councillor_role_id',
        RoleType.CHANCELLOR: 'chancellor_role_id',
        RoleType.MINISTER: 'minister_role_id',
        RoleType.JUDICIARY: 'judiciary_role_id',
        RoleType.PRESIDENT: 'president_role_id',
        RoleType.VICE_PRESIDENT: 'vice_president_role_id'
    }

    role_field = role_field_map.get(role)
    if not role_field or not guild_data.get(role_field):
        return False

    role_id = guild_data[role_field]
    discord_role = guild.get_role(int(role_id))

    if discord_role and discord_role in user.roles:
        return True

    return False


async def check_councillor(
    user: discord.Member,
    guild: discord.Guild,
    db_helper: DatabaseHelper
) -> None:
    """
    Check if user is a councillor, raise exception if not

    Args:
        user: Discord member to check
        guild: Discord guild
        db_helper: Database helper instance

    Raises:
        NotEligibleError: If user is not a councillor
    """
    if not await is_eligible(user, guild, RoleType.COUNCILLOR, db_helper):
        if not await is_admin(user):
            raise NotEligibleError("You must be a Councillor to perform this action.")


async def check_chancellor(
    user: discord.Member,
    guild: discord.Guild,
    db_helper: DatabaseHelper
) -> None:
    """
    Check if user is the chancellor, raise exception if not

    Args:
        user: Discord member to check
        guild: Discord guild
        db_helper: Database helper instance

    Raises:
        NotEligibleError: If user is not the chancellor
    """
    if not await is_eligible(user, guild, RoleType.CHANCELLOR, db_helper):
        if not await is_admin(user):
            raise NotEligibleError("You must be the Chancellor to perform this action.")


async def check_president(
    user: discord.Member,
    guild: discord.Guild,
    db_helper: DatabaseHelper
) -> None:
    """
    Check if user is president or vice president, raise exception if not

    Args:
        user: Discord member to check
        guild: Discord guild
        db_helper: Database helper instance

    Raises:
        NotEligibleError: If user is not president or vice president
    """
    is_pres = await is_eligible(user, guild, RoleType.PRESIDENT, db_helper)
    is_vice = await is_eligible(user, guild, RoleType.VICE_PRESIDENT, db_helper)

    if not (is_pres or is_vice) and not await is_admin(user):
        raise NotEligibleError("You must be a President or Vice President to perform this action.")


async def check_admin(user: discord.User | discord.Member) -> None:
    """
    Check if user is an admin, raise exception if not

    Args:
        user: Discord user to check

    Raises:
        PermissionError: If user is not an admin
    """
    if not await is_admin(user):
        raise PermissionError("You must be an admin to perform this action.")


async def can_register_to_vote(
    user: discord.Member,
    guild: discord.Guild,
    db_helper: DatabaseHelper
) -> tuple[bool, str]:
    """
    Check if user can register to vote in elections

    Args:
        user: Discord member to check
        guild: Discord guild
        db_helper: Database helper instance

    Returns:
        Tuple of (can_register, reason_if_not)
    """
    guild_data = await db_helper.get_guild(guild.id)

    if not guild_data:
        return False, "Guild data not found"

    # Check days requirement
    days_req = guild_data.get('days_requirement', 180)

    if user.joined_at:
        from datetime import datetime, timezone
        days_in_server = (datetime.now(timezone.utc) - user.joined_at).days

        if days_in_server < days_req:
            return False, f"You must be a member for at least {days_req} days. You have been here for {days_in_server} days."

    # Check if they have the required role (if set)
    if guild_data.get('citizen_role_id'):
        required_role = guild.get_role(int(guild_data['citizen_role_id']))
        if required_role and required_role not in user.roles:
            return False, f"You must have the {required_role.name} role to participate."

    return True, ""


async def can_run_for_councillor(
    user: discord.Member,
    guild: discord.Guild,
    db_helper: DatabaseHelper
) -> tuple[bool, str]:
    """
    Check if user can run for councillor

    Args:
        user: Discord member to check
        guild: Discord guild
        db_helper: Database helper instance

    Returns:
        Tuple of (can_run, reason_if_not)
    """
    # Same requirements as voting for now
    return await can_register_to_vote(user, guild, db_helper)


def command_check_admin():
    """Decorator to check if user is admin"""
    async def predicate(interaction: discord.Interaction) -> bool:
        return await is_admin(interaction.user)
    return discord.app_commands.check(predicate)


def command_check_councillor(db_helper: DatabaseHelper):
    """Decorator to check if user is councillor"""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            return False
        return await is_eligible(interaction.user, interaction.guild, RoleType.COUNCILLOR, db_helper)
    return discord.app_commands.check(predicate)


def command_check_chancellor(db_helper: DatabaseHelper):
    """Decorator to check if user is chancellor"""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            return False
        return await is_eligible(interaction.user, interaction.guild, RoleType.CHANCELLOR, db_helper)
    return discord.app_commands.check(predicate)
"""
Error handling utilities for the Councillor Discord Bot
Provides consistent error handling and user-friendly error messages
"""
import sys
import traceback
from typing import Optional

import discord
from discord.ext import commands

from utils.formatting import create_error_message, create_warning_message


class CouncillorException(Exception):
    """Base exception for Councillor bot"""
    pass


class NotEligibleError(CouncillorException):
    """User is not eligible for the action"""
    pass


class AlreadyExistsError(CouncillorException):
    """Resource already exists"""
    pass


class NotFoundError(CouncillorException):
    """Resource not found"""
    pass


class InvalidInputError(CouncillorException):
    """Invalid input provided"""
    pass


class PermissionError(CouncillorException):
    """User lacks required permissions"""
    pass


async def handle_interaction_error(
    interaction: discord.Interaction,
    error: Optional[Exception] = None,
    custom_message: Optional[str] = None,
    ephemeral: bool = True,
    log_error: bool = True
) -> None:
    """
    Global error handling function for interactions.

    Args:
        interaction: The Discord interaction
        error: The exception that occurred (optional)
        custom_message: A custom error message to display (optional)
        ephemeral: Whether the message should be ephemeral (default: True)
        log_error: Whether to log the error (default: True)
    """
    # Default error message
    message = create_error_message("An unexpected error occurred. Please try again later.")

    # Handle specific error types
    if error:
        if isinstance(error, NotEligibleError):
            message = create_error_message(str(error))
        elif isinstance(error, AlreadyExistsError):
            message = create_warning_message(str(error))
        elif isinstance(error, NotFoundError):
            message = create_error_message(str(error))
        elif isinstance(error, InvalidInputError):
            message = create_error_message(str(error))
        elif isinstance(error, PermissionError):
            message = create_error_message(str(error))
        elif isinstance(error, discord.errors.Forbidden):
            message = create_error_message(
                "Missing Permissions! The bot doesn't have the required permissions to perform this action."
            )
        elif isinstance(error, discord.errors.NotFound):
            message = create_error_message("Not Found! The requested resource could not be found.")
        elif isinstance(error, discord.errors.HTTPException):
            message = create_error_message(f"Discord API Error! {error.status}: {error.text}")
        elif isinstance(error, commands.MissingRequiredArgument):
            message = create_error_message(f"Missing Argument! The parameter `{error.param.name}` is required.")
        elif isinstance(error, commands.CommandOnCooldown):
            message = create_warning_message(
                f"Command on Cooldown! Please try again in {error.retry_after:.1f} seconds."
            )
        elif isinstance(error, commands.MissingPermissions):
            message = create_error_message(
                "Missing Permissions! You don't have the required permissions to use this command."
            )

        # Log the full error for debugging
        if log_error and not isinstance(error, CouncillorException):
            print(f"Error in interaction: {error}")
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    # Use custom message if provided
    if custom_message:
        message = custom_message

    try:
        # Try to respond to the interaction
        if not interaction.response.is_done():
            await interaction.response.send_message(message, ephemeral=ephemeral)
        else:
            # If the interaction was already responded to, use followup
            await interaction.followup.send(message, ephemeral=ephemeral)
    except Exception as e:
        # If responding to the interaction fails, try to send a message to the channel
        try:
            if interaction.channel:
                await interaction.channel.send(message)
        except Exception as channel_error:
            # If all else fails, just log the error
            print(f"Failed to send error message: {e}")
            if error:
                print(f"Original error: {error}")
            print(f"Channel send error: {channel_error}")


async def handle_command_error(ctx: commands.Context, error: Exception) -> None:
    """
    Handle errors in text commands

    Args:
        ctx: Command context
        error: The exception that occurred
    """
    message = create_error_message("An unexpected error occurred. Please try again later.")

    if isinstance(error, commands.CommandNotFound):
        return  # Silently ignore command not found
    elif isinstance(error, commands.MissingRequiredArgument):
        message = create_error_message(f"Missing Argument! The parameter `{error.param.name}` is required.")
    elif isinstance(error, commands.BadArgument):
        message = create_error_message(f"Invalid Argument! {str(error)}")
    elif isinstance(error, commands.CommandOnCooldown):
        message = create_warning_message(f"Command on Cooldown! Please try again in {error.retry_after:.1f} seconds.")
    elif isinstance(error, commands.MissingPermissions):
        message = create_error_message("Missing Permissions! You don't have the required permissions to use this command.")
    elif isinstance(error, commands.BotMissingPermissions):
        message = create_error_message("Bot Missing Permissions! The bot doesn't have the required permissions.")
    else:
        print(f"Unhandled command error: {error}")
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    try:
        await ctx.send(message)
    except Exception:
        pass  # Silently fail if we can't send the error message

