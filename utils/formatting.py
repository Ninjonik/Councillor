"""
Discord formatting utilities
Provides consistent, modern Discord markdown formatting
"""
import discord
from typing import Optional
from datetime import datetime


def format_heading(text: str, level: int = 1) -> str:
    """
    Format text as a heading using Discord markdown

    Args:
        text: The text to format
        level: Heading level (1-3)

    Returns:
        Formatted heading string
    """
    if level == 1:
        return f"# {text}"
    elif level == 2:
        return f"## {text}"
    elif level == 3:
        return f"### {text}"
    else:
        return f"**{text}**"


def format_bold(text: str) -> str:
    """Format text as bold"""
    return f"**{text}**"


def format_italic(text: str) -> str:
    """Format text as italic"""
    return f"*{text}*"


def format_code(text: str, language: str = "") -> str:
    """Format text as code block"""
    return f"```{language}\n{text}\n```"


def format_inline_code(text: str) -> str:
    """Format text as inline code"""
    return f"`{text}`"


def format_quote(text: str) -> str:
    """Format text as a quote"""
    return f"> {text}"


def format_list_item(text: str, ordered: bool = False, number: int = 1) -> str:
    """Format text as a list item"""
    if ordered:
        return f"{number}. {text}"
    return f"- {text}"


def format_timestamp(dt: datetime, style: str = "F") -> str:
    """
    Format a datetime as a Discord timestamp

    Styles:
    - t: Short Time (16:20)
    - T: Long Time (16:20:30)
    - d: Short Date (20/04/2021)
    - D: Long Date (20 April 2021)
    - f: Short Date/Time (20 April 2021 16:20)
    - F: Long Date/Time (Tuesday, 20 April 2021 16:20)
    - R: Relative Time (2 months ago)
    """
    timestamp = int(dt.timestamp())
    return f"<t:{timestamp}:{style}>"


def format_user_mention(user_id: int) -> str:
    """Format a user mention"""
    return f"<@{user_id}>"


def format_role_mention(role_id: int) -> str:
    """Format a role mention"""
    return f"<@&{role_id}>"


def format_channel_mention(channel_id: int) -> str:
    """Format a channel mention"""
    return f"<#{channel_id}>"


def create_success_message(text: str) -> str:
    """Create a success message with consistent formatting"""
    return f"✅ {format_bold('Success!')} {text}"


def create_error_message(text: str) -> str:
    """Create an error message with consistent formatting"""
    return f"❌ {format_bold('Error!')} {text}"


def create_warning_message(text: str) -> str:
    """Create a warning message with consistent formatting"""
    return f"⚠️ {format_bold('Warning!')} {text}"


def create_info_message(text: str) -> str:
    """Create an info message with consistent formatting"""
    return f"ℹ️ {format_bold('Info:')} {text}"


def format_voting_result(passed: bool, yes_count: int, no_count: int, required_percentage: float) -> str:
    """Format voting results consistently"""
    status = format_bold("PASSED ✅") if passed else format_bold("FAILED ❌")
    return (f"{status}\n\n"
            f"**Voting Results:**\n"
            f"✅ For: {yes_count}\n"
            f"❌ Against: {no_count}\n"
            f"📊 Required: >{required_percentage * 100:.0f}%")


def create_embed(
    title: str,
    description: Optional[str] = None,
    color: Optional[int] = None,
    author_name: Optional[str] = None,
    author_icon: Optional[str] = None,
    footer_text: Optional[str] = None,
    footer_icon: Optional[str] = None,
    thumbnail: Optional[str] = None,
    image: Optional[str] = None,
    timestamp: Optional[datetime] = None
) -> discord.Embed:
    """
    Create a consistently formatted embed

    Args:
        title: Embed title
        description: Embed description
        color: Embed color (hex or int)
        author_name: Author name
        author_icon: Author icon URL
        footer_text: Footer text
        footer_icon: Footer icon URL
        thumbnail: Thumbnail URL
        image: Image URL
        timestamp: Timestamp

    Returns:
        Configured Discord embed
    """
    if color is None:
        color = discord.Color.blue()
    elif isinstance(color, int):
        color = discord.Color(color)

    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=timestamp
    )

    if author_name:
        embed.set_author(name=author_name, icon_url=author_icon)

    if footer_text:
        embed.set_footer(text=footer_text, icon_url=footer_icon)

    if thumbnail:
        embed.set_thumbnail(url=thumbnail)

    if image:
        embed.set_image(url=image)

    return embed


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to a maximum length"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix
# Utils package for Councillor bot

