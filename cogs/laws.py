"""
Laws and Decrees Commands Cog
Lists passed/failed laws, manages decrees, and stores constitution markdown.
"""
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, cast
from datetime import datetime

import config
from utils.database import DatabaseHelper
from utils.permissions import check_admin, check_executive
from utils.errors import handle_interaction_error, InvalidInputError
from utils.helpers import convert_datetime_from_str, datetime_now
from utils.formatting import create_success_message, create_error_message, create_embed, format_timestamp
from utils.enums import VotingStatus, LogType, SettingType, EditableBy


def _web_base_url() -> str:
    host = getattr(config, "WEB_PUBLIC_BASE_URL", None)
    if host:
        return host.rstrip("/")
    port = getattr(config, "WEB_PORT", 7029)
    return f"http://localhost:{port}"


def _short(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    if width <= 1:
        return value[:width]
    return value[: width - 1] + "~"


class DetailsLinksView(discord.ui.View):
    """Adds URL buttons for item details pages."""

    def __init__(self, links: list[tuple[str, str]]):
        super().__init__(timeout=None)
        for index, (label, url) in enumerate(links[:10], start=1):
            button = discord.ui.Button(
                label=f"{index}. {label[:35]}",
                style=discord.ButtonStyle.link,
                url=url,
            )
            self.add_item(button)


class Laws(commands.Cog):
    """Commands for law/decree history and constitutional text."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_helper = cast(DatabaseHelper, getattr(bot, "db_helper"))

    @app_commands.command(name="laws", description="List passed/failed laws with vote counts")
    @app_commands.describe(status="Filter by law status")
    @app_commands.choices(status=[
        app_commands.Choice(name="Passed", value="passed"),
        app_commands.Choice(name="Failed", value="failed"),
        app_commands.Choice(name="Both", value="both"),
    ])
    async def laws(
        self,
        interaction: discord.Interaction,
        status: Optional[app_commands.Choice[str]] = None,
    ):
        """Show a table-like list of laws with vote counts and details links."""
        try:
            await interaction.response.defer(ephemeral=True, thinking=True)

            status_value = status.value if status else "both"
            statuses = [VotingStatus.PASSED, VotingStatus.FAILED]
            if status_value == "passed":
                statuses = [VotingStatus.PASSED]
            elif status_value == "failed":
                statuses = [VotingStatus.FAILED]

            laws = await self.db_helper.list_laws(interaction.guild.id, statuses=statuses, limit=50)
            laws.sort(key=lambda law: law.get("voting_end", ""), reverse=True)

            if not laws:
                await interaction.followup.send(
                    create_error_message("No laws found for the selected status."),
                    ephemeral=True,
                )
                return

            table_lines = [
                "Idx  Status  Yes  No   End(UTC)         Title",
                "---- ------ ---  ---  ---------------  ------------------------------",
            ]
            links: list[tuple[str, str]] = []
            base_url = _web_base_url()

            for index, law in enumerate(laws[:15], start=1):
                votes = await self.db_helper.get_votes_for_voting(law["$id"])
                yes_votes = sum(1 for vote in votes if vote.get("stance", False))
                no_votes = len(votes) - yes_votes
                status_label = "PASS" if law.get("status") == VotingStatus.PASSED.value else "FAIL"

                end_text = "-"
                raw_end = law.get("voting_end")
                if raw_end:
                    try:
                        end_dt = datetime.fromisoformat(raw_end.replace("Z", "+00:00"))
                        end_text = end_dt.strftime("%Y-%m-%d %H:%M")
                    except ValueError:
                        end_text = raw_end[:16]

                title = _short(law.get("title", "Untitled"), 30)
                table_lines.append(f"{index:<4} {status_label:<6} {yes_votes:<4} {no_votes:<4} {end_text:<16}  {title}")
                links.append((law.get("title", "Law"), f"{base_url}/g/{interaction.guild.id}/laws/{law['$id']}.md"))

            content = "```\n" + "\n".join(table_lines) + "\n```"
            await interaction.followup.send(content=content, view=DetailsLinksView(links), ephemeral=True)

        except Exception as e:
            await handle_interaction_error(interaction, e)

    @app_commands.command(name="decrees", description="List decrees currently in effect or historical")
    @app_commands.describe(scope="Which decrees to show")
    @app_commands.choices(scope=[
        app_commands.Choice(name="Currently in effect", value="active"),
        app_commands.Choice(name="Past decrees", value="history"),
    ])
    async def decrees(self, interaction: discord.Interaction, scope: app_commands.Choice[str]):
        """List decrees with title-only rows and detail links."""
        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
            await self.db_helper.expire_decrees(interaction.guild.id)

            active_only = True if scope.value == "active" else False
            decrees = await self.db_helper.list_decrees(interaction.guild.id, active_only=active_only, limit=50)
            decrees.sort(key=lambda decree: decree.get("issued_at", ""), reverse=True)

            if not decrees:
                msg = "No active decrees." if active_only else "No historical decrees yet."
                await interaction.followup.send(create_error_message(msg), ephemeral=True)
                return

            table_lines = [
                "Idx  Active  Expires(UTC)      Title",
                "---- ------  ----------------  ------------------------------",
            ]
            links: list[tuple[str, str]] = []
            base_url = _web_base_url()

            for index, decree in enumerate(decrees[:15], start=1):
                expires = decree.get("expires_at")
                expires_text = "No expiry"
                if expires:
                    try:
                        expires_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                        expires_text = expires_dt.strftime("%Y-%m-%d %H:%M")
                    except ValueError:
                        expires_text = expires[:16]

                active_label = "YES" if decree.get("active", False) else "NO"
                title = _short(decree.get("title", "Untitled"), 30)
                table_lines.append(f"{index:<4} {active_label:<6}  {expires_text:<16}  {title}")
                links.append((decree.get("title", "Decree"), f"{base_url}/g/{interaction.guild.id}/decrees/{decree['$id']}.md"))

            content = "```\n" + "\n".join(table_lines) + "\n```"
            await interaction.followup.send(content=content, view=DetailsLinksView(links), ephemeral=True)

        except Exception as e:
            await handle_interaction_error(interaction, e)

    @app_commands.command(name="issue_decree", description="[Executive] Issue a decree without council voting")
    @app_commands.describe(
        title="Decree title",
        description="Decree content",
        expires_at="Optional expiry (DD.MM.YYYY HH:MM, UTC)",
    )
    async def issue_decree(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        expires_at: Optional[str] = None,
    ):
        """Issue a decree and mark it active until optional expiry."""
        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
            await check_executive(interaction.user, interaction.guild, self.db_helper)

            expiry_dt = None
            if expires_at:
                expiry_dt = convert_datetime_from_str(expires_at)
                if not expiry_dt:
                    raise InvalidInputError("Invalid date format. Use DD.MM.YYYY HH:MM")
                if expiry_dt <= datetime_now():
                    raise InvalidInputError("Expiry must be in the future.")

            decree = await self.db_helper.create_decree(
                guild_id=interaction.guild.id,
                title=title,
                description=description,
                issued_by=interaction.user.id,
                issued_by_name=interaction.user.name,
                expires_at=expiry_dt,
            )

            await self.db_helper.log(
                guild_id=interaction.guild.id,
                log_type=LogType.COMMAND,
                action="issue_decree",
                discord_id=interaction.user.id,
                details={"decree_id": decree["$id"], "title": title},
            )

            base_url = _web_base_url()
            details_url = f"{base_url}/g/{interaction.guild.id}/decrees/{decree['$id']}.md"
            expiry_text = format_timestamp(expiry_dt, "F") if expiry_dt else "No expiry"

            embed = create_embed(
                title="Executive Decree Issued",
                description=(
                    f"**Title:** {title}\n"
                    f"**In Effect:** Yes\n"
                    f"**Expires:** {expiry_text}\n"
                    f"[View More Details]({details_url})"
                ),
                color=0xFFB347,
                timestamp=datetime_now(),
            )

            guild_data = await self.db_helper.get_guild(interaction.guild.id)
            channel_id = guild_data.get("announcement_channel_id") or guild_data.get("voting_channel_id")
            if channel_id:
                channel = interaction.guild.get_channel(int(channel_id))
                if channel:
                    await channel.send(embed=embed)

            await interaction.followup.send(create_success_message("Decree issued successfully."), ephemeral=True)

        except Exception as e:
            await handle_interaction_error(interaction, e)

    @app_commands.command(name="set_constitution", description="[Admin] Set constitution markdown for this server")
    @app_commands.describe(
        markdown="Constitution text in markdown (optional if file provided)",
        markdown_file="Optional .md or .txt file with constitution",
    )
    async def set_constitution(
        self,
        interaction: discord.Interaction,
        markdown: Optional[str] = None,
        markdown_file: Optional[discord.Attachment] = None,
    ):
        """Set constitution markdown stored in Appwrite settings."""
        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
            await check_admin(interaction.user)

            text = markdown or ""
            if markdown_file:
                data = await markdown_file.read()
                try:
                    text = data.decode("utf-8")
                except UnicodeDecodeError:
                    raise InvalidInputError("Constitution file must be UTF-8 text.")

            if not text.strip():
                raise InvalidInputError("Provide markdown text or upload a markdown file.")

            await self.db_helper.set_setting(
                key="constitution_markdown",
                value=text,
                guild_id=interaction.guild.id,
                setting_type=SettingType.STRING,
                description="Constitution markdown for public pages",
                editable_by=EditableBy.ADMIN,
            )

            await self.db_helper.log(
                guild_id=interaction.guild.id,
                log_type=LogType.ADMIN,
                action="set_constitution",
                discord_id=interaction.user.id,
                details={"length": len(text)},
            )

            base_url = _web_base_url()
            await interaction.followup.send(
                create_success_message(
                    f"Constitution updated. View it at {base_url}/g/{interaction.guild.id}/constitution.md"
                ),
                ephemeral=True,
            )

        except Exception as e:
            await handle_interaction_error(interaction, e)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Laws(bot))
