"""
Public Markdown Web Server Cog
Serves per-guild markdown pages for laws, decrees, and constitution.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, cast
import html

import markdown as md
from aiohttp import web
from discord.ext import commands

import config
from utils.database import DatabaseHelper
from utils.enums import VotingStatus


def _render_breadcrumbs(breadcrumbs: list[tuple[str, Optional[str]]]) -> str:
    parts: list[str] = []
    for i, (label, href) in enumerate(breadcrumbs):
        safe_label = html.escape(label)
        if href:
            parts.append(f'<a href="{html.escape(href)}">{safe_label}</a>')
        else:
            parts.append(f'<span class="current">{safe_label}</span>')
        if i < len(breadcrumbs) - 1:
            parts.append('<span class="sep">/</span>')
    return "".join(parts)


def _render_html_page(
    title: str,
    markdown_text: str,
    breadcrumbs: Optional[list[tuple[str, Optional[str]]]] = None,
) -> str:
    body_html = md.markdown(
        markdown_text,
        extensions=["extra", "tables", "fenced_code", "nl2br"],
    )
    safe_title = html.escape(title)
    crumbs = _render_breadcrumbs(breadcrumbs or [("Home", "/"), (title, None)])
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{safe_title}</title>
  <style>
    :root {{
      --bg: #f7f8fb;
      --fg: #151826;
      --muted: #6b7280;
      --card: #ffffff;
      --card-border: #dfe3eb;
      --link: #0f6ad8;
      --code-bg: #eef2ff;
      --pre-bg: #f3f4f6;
      --pre-border: #d1d5db;
      --table-border: #d1d5db;
      --table-head: #eef2ff;
      --crumb-bg: #f3f4f6;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #0f1220;
        --fg: #e6eaf2;
        --muted: #a4acc4;
        --card: #171b2e;
        --card-border: #262b45;
        --link: #8ecbff;
        --code-bg: #232845;
        --pre-bg: #111527;
        --pre-border: #2a3155;
        --table-border: #30375f;
        --table-head: #212848;
        --crumb-bg: #12172b;
      }}
    }}
    body {{ font-family: Inter, Segoe UI, Arial, sans-serif; margin: 0; background: var(--bg); color: var(--fg); }}
    .wrap {{ max-width: 980px; margin: 0 auto; padding: 22px; }}
    .nav {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 12px; }}
    .crumbs {{ background: var(--crumb-bg); border: 1px solid var(--card-border); border-radius: 8px; padding: 8px 10px; font-size: 0.95rem; }}
    .crumbs .sep {{ margin: 0 8px; color: var(--muted); }}
    .crumbs .current {{ color: var(--fg); font-weight: 700; }}
    .back-btn {{ border: 1px solid var(--card-border); background: var(--card); color: var(--fg); border-radius: 8px; padding: 7px 10px; cursor: pointer; }}
    .back-btn:hover {{ border-color: var(--link); }}
    .card {{ background: var(--card); border: 1px solid var(--card-border); border-radius: 10px; padding: 18px 22px; }}
    a {{ color: var(--link); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    h1, h2, h3 {{ color: var(--fg); }}
    code {{ background: var(--code-bg); border-radius: 4px; padding: 2px 5px; }}
    pre {{ background: var(--pre-bg); border: 1px solid var(--pre-border); border-radius: 8px; padding: 12px; overflow-x: auto; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
    th, td {{ border: 1px solid var(--table-border); padding: 8px; text-align: left; }}
    th {{ background: var(--table-head); }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <div class=\"nav\">
      <div class=\"crumbs\">{crumbs}</div>
      <button class=\"back-btn\" onclick=\"history.back()\">Back</button>
    </div>
    <div class=\"card\">{body_html}</div>
  </div>
</body>
</html>
"""


def _md_response(
    text: str,
    title: str = "Councillor Public Pages",
    breadcrumbs: Optional[list[tuple[str, Optional[str]]]] = None,
) -> web.Response:
    return web.Response(
        text=_render_html_page(title, text, breadcrumbs=breadcrumbs),
        content_type="text/html",
    )


class WebServer(commands.Cog):
    """Runs a small aiohttp server alongside the bot."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_helper = cast(DatabaseHelper, getattr(bot, "db_helper"))
        self.host = getattr(config, "WEB_HOST", "0.0.0.0")
        self.port = int(getattr(config, "WEB_PORT", 8089))
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None

    async def cog_load(self):
        self.bot.loop.create_task(self._start_server())

    async def cog_unload(self):
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
            self._site = None

    async def _start_server(self):
        await self.bot.wait_until_ready()
        if self._runner:
            return

        app = web.Application()
        app.router.add_get("/", self.home)
        app.router.add_get("/g/{guild_id}", self.guild_home)
        app.router.add_get("/g/{guild_id}/constitution.md", self.constitution)
        app.router.add_get("/g/{guild_id}/laws/passed.md", self.laws_passed)
        app.router.add_get("/g/{guild_id}/laws/failed.md", self.laws_failed)
        app.router.add_get("/g/{guild_id}/laws/{law_id}.md", self.law_details)
        app.router.add_get("/g/{guild_id}/decrees/active.md", self.decrees_active)
        app.router.add_get("/g/{guild_id}/decrees/history.md", self.decrees_history)
        app.router.add_get("/g/{guild_id}/decrees/{decree_id}.md", self.decree_details)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, host=self.host, port=self.port)
        await self._site.start()
        print(f"[WEB] Markdown server started on {self.host}:{self.port}")

    async def _guild_header(self, guild_id: int) -> str:
        guild = self.bot.get_guild(guild_id)
        guild_name = guild.name if guild else f"Guild {guild_id}"
        return f"# {guild_name}\n\n"

    async def home(self, request: web.Request) -> web.Response:
        lines = ["# Councillor Public Pages", "", "Select a server:"]
        for guild in self.bot.guilds:
            lines.append(f"- [{guild.name}](/g/{guild.id})")
        if not self.bot.guilds:
            lines.append("- No guilds are currently available.")
        return _md_response(
            "\n".join(lines) + "\n",
            title="Councillor Public Pages",
            breadcrumbs=[("Home", None)],
        )

    async def guild_home(self, request: web.Request) -> web.Response:
        guild_id = int(request.match_info["guild_id"])
        text = (
            await self._guild_header(guild_id)
            + "## Navigation\n"
            + f"- [Constitution](/g/{guild_id}/constitution.md)\n"
            + f"- [Passed Laws](/g/{guild_id}/laws/passed.md)\n"
            + f"- [Failed Laws](/g/{guild_id}/laws/failed.md)\n"
            + f"- [Current Decrees](/g/{guild_id}/decrees/active.md)\n"
            + f"- [Past Decrees](/g/{guild_id}/decrees/history.md)\n"
        )
        return _md_response(
            text,
            title=f"Guild {guild_id} • Navigation",
            breadcrumbs=[("Home", "/"), (f"Guild {guild_id}", None)],
        )

    async def constitution(self, request: web.Request) -> web.Response:
        guild_id = int(request.match_info["guild_id"])
        setting = await self.db_helper.get_setting("constitution_markdown", guild_id)
        title = await self._guild_header(guild_id)
        crumbs = [("Home", "/"), (f"Guild {guild_id}", f"/g/{guild_id}"), ("Constitution", None)]
        if not setting:
            return _md_response(
                title + "## Constitution\n\n_Not configured yet._\n",
                title="Constitution",
                breadcrumbs=crumbs,
            )
        return _md_response(
            title + setting.get("value", "_Empty constitution._") + "\n",
            title="Constitution",
            breadcrumbs=crumbs,
        )

    async def _laws_page(self, guild_id: int, status: VotingStatus) -> web.Response:
        laws = await self.db_helper.list_laws(guild_id, statuses=[status], limit=100)
        laws.sort(key=lambda law: law.get("voting_end", ""), reverse=True)

        title = "Passed Laws" if status == VotingStatus.PASSED else "Failed Laws"
        lines = [await self._guild_header(guild_id), f"## {title}", ""]

        crumbs = [("Home", "/"), (f"Guild {guild_id}", f"/g/{guild_id}"), (title, None)]
        if not laws:
            lines.append("_No entries found._")
            return _md_response("\n".join(lines) + "\n", title=title, breadcrumbs=crumbs)

        for law in laws:
            votes = await self.db_helper.get_votes_for_voting(law["$id"])
            yes_votes = sum(1 for vote in votes if vote.get("stance", False))
            no_votes = len(votes) - yes_votes
            lines.append(f"- **{law.get('title', 'Untitled')}** — yes: {yes_votes}, no: {no_votes} ([details](/g/{guild_id}/laws/{law['$id']}.md))")

        return _md_response("\n".join(lines) + "\n", title=title, breadcrumbs=crumbs)

    async def laws_passed(self, request: web.Request) -> web.Response:
        guild_id = int(request.match_info["guild_id"])
        return await self._laws_page(guild_id, VotingStatus.PASSED)

    async def laws_failed(self, request: web.Request) -> web.Response:
        guild_id = int(request.match_info["guild_id"])
        return await self._laws_page(guild_id, VotingStatus.FAILED)

    async def law_details(self, request: web.Request) -> web.Response:
        guild_id = int(request.match_info["guild_id"])
        law_id = request.match_info["law_id"]
        law = await self.db_helper.get_voting(law_id)
        if not law:
            raise web.HTTPNotFound(text="Law not found")

        votes = await self.db_helper.get_votes_for_voting(law_id)
        yes_votes = sum(1 for vote in votes if vote.get("stance", False))
        no_votes = len(votes) - yes_votes

        end_text = law.get("voting_end", "Unknown")
        try:
            end_text = datetime.fromisoformat(end_text.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            pass

        text = (
            await self._guild_header(guild_id)
            + "## Law Details\n\n"
            + f"**Title:** {law.get('title', 'Untitled')}\n\n"
            + f"**Type:** {law.get('type', 'unknown')}\n\n"
            + f"**Status:** {law.get('status', 'unknown')}\n\n"
            + f"**Voting End:** {end_text}\n\n"
            + f"**Votes:** yes={yes_votes}, no={no_votes}\n\n"
            + "### Description\n\n"
            + (law.get("description") or "_No description provided._")
            + "\n"
        )
        detail_title = law.get("title", f"Law {law_id}")
        crumbs = [
            ("Home", "/"),
            (f"Guild {guild_id}", f"/g/{guild_id}"),
            ("Laws", f"/g/{guild_id}/laws/passed.md"),
            (detail_title, None),
        ]
        return _md_response(text, title=detail_title, breadcrumbs=crumbs)

    async def _decrees_page(self, guild_id: int, active_only: bool) -> web.Response:
        await self.db_helper.expire_decrees(guild_id)
        decrees = await self.db_helper.list_decrees(guild_id, active_only=active_only, limit=100)
        decrees.sort(key=lambda decree: decree.get("issued_at", ""), reverse=True)

        title = "Current Decrees" if active_only else "Past Decrees"
        lines = [await self._guild_header(guild_id), f"## {title}", ""]
        crumbs = [("Home", "/"), (f"Guild {guild_id}", f"/g/{guild_id}"), (title, None)]
        if not decrees:
            lines.append("_No entries found._")
            return _md_response("\n".join(lines) + "\n", title=title, breadcrumbs=crumbs)

        for decree in decrees:
            lines.append(
                f"- **{decree.get('title', 'Untitled')}** ([details](/g/{guild_id}/decrees/{decree['$id']}.md))"
            )

        return _md_response("\n".join(lines) + "\n", title=title, breadcrumbs=crumbs)

    async def decrees_active(self, request: web.Request) -> web.Response:
        guild_id = int(request.match_info["guild_id"])
        return await self._decrees_page(guild_id, True)

    async def decrees_history(self, request: web.Request) -> web.Response:
        guild_id = int(request.match_info["guild_id"])
        return await self._decrees_page(guild_id, False)

    async def decree_details(self, request: web.Request) -> web.Response:
        guild_id = int(request.match_info["guild_id"])
        decree_id = request.match_info["decree_id"]
        decree = await self.db_helper.get_decree(decree_id)
        if not decree:
            raise web.HTTPNotFound(text="Decree not found")

        text = (
            await self._guild_header(guild_id)
            + "## Decree Details\n\n"
            + f"**Title:** {decree.get('title', 'Untitled')}\n\n"
            + f"**Issued By:** {decree.get('issued_by_name', 'Unknown')}\n\n"
            + f"**Active:** {'Yes' if decree.get('active', False) else 'No'}\n\n"
            + f"**Issued At:** {decree.get('issued_at', 'Unknown')}\n\n"
            + f"**Expires At:** {decree.get('expires_at', 'No expiry')}\n\n"
            + "### Description\n\n"
            + (decree.get("description") or "_No description provided._")
            + "\n"
        )
        detail_title = decree.get("title", f"Decree {decree_id}")
        crumbs = [
            ("Home", "/"),
            (f"Guild {guild_id}", f"/g/{guild_id}"),
            ("Decrees", f"/g/{guild_id}/decrees/active.md"),
            (detail_title, None),
        ]
        return _md_response(text, title=detail_title, breadcrumbs=crumbs)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WebServer(bot))
