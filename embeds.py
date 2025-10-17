import discord
from datetime import datetime
from typing import Optional

def create_success_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(
        title=f"✅ {title}",
        description=description,
        color=0x00FF00,
        timestamp=datetime.now(datetime.UTC) if hasattr(datetime, 'UTC') else datetime.utcnow()
    )

def create_error_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(
        title=f"❌ {title}",
        description=description,
        color=0xFF0000,
        timestamp=datetime.now(datetime.UTC) if hasattr(datetime, 'UTC') else datetime.utcnow()
    )

def create_info_embed(title: str, description: str, color: int = 0x3498DB) -> discord.Embed:
    return discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.now(datetime.UTC) if hasattr(datetime, 'UTC') else datetime.utcnow()
    )

def create_council_info_embed(guild: discord.Guild, chancellor: str, council_members: list) -> discord.Embed:
    embed = discord.Embed(
        title="🏛️ The Grand Council",
        description=f"The Grand Council is the legislative body of **{guild.name}**, consisting of elected "
                    f"Members of Parliament (MPs) who vote on laws, policies, and constitutional matters. "
                    f"The Chancellor leads the executive branch and can veto legislation, though the Council "
                    f"may override with a 2/3 majority.",
        color=0x2ECC71
    )

    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    embed.add_field(
        name="👑 Current Chancellor",
        value=chancellor or "None appointed",
        inline=False
    )

    if council_members:
        embed.add_field(
            name=f"📋 Council Members ({len(council_members)}/12)",
            value=", ".join(council_members) if len(council_members) <= 12 else ", ".join(council_members[:12]) + "...",
            inline=False
        )
    else:
        embed.add_field(
            name="📋 Council Members",
            value="No councillors currently seated",
            inline=False
        )

    embed.set_footer(text="Use /council to join or learn more")
    return embed

def create_voting_embed(
    title: str,
    description: str,
    voting_type: dict,
    author: discord.Member,
    voting_end: datetime,
    voting_id: Optional[str] = None
) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=description,
        color=voting_type["color"]
    )

    embed.set_author(
        name=author.display_name,
        icon_url=author.avatar.url if author.avatar else None
    )

    embed.add_field(
        name="📊 Type",
        value=f"{voting_type['emoji']} {voting_type['text']}",
        inline=True
    )

    embed.add_field(
        name="⏰ Ends",
        value=f"<t:{int(voting_end.timestamp())}:R>",
        inline=True
    )

    embed.add_field(
        name="✅ Required",
        value=f"{voting_type['required_percentage']*100:.0f}%",
        inline=True
    )

    footer_text = f"Vote ends: {voting_end.strftime('%d.%m.%Y %H:%M')} UTC"
    if voting_id:
        footer_text += f" | ID: {voting_id}"

    embed.set_footer(text=footer_text)
    return embed

def create_voting_result_embed(
    title: str,
    description: str,
    passed: bool,
    positive_votes: int,
    negative_votes: int,
    required_percentage: float,
    proposer_name: Optional[str] = None
) -> discord.Embed:
    color = 0x00FF00 if passed else 0xFF0000
    result_emoji = "✅" if passed else "❌"

    embed = discord.Embed(
        title=f"{result_emoji} {title}",
        description=description,
        color=color
    )

    total = positive_votes + negative_votes
    for_percentage = (positive_votes / total * 100) if total > 0 else 0

    embed.add_field(
        name="📊 Final Result",
        value=f"**{'PASSED' if passed else 'FAILED'}**",
        inline=False
    )

    embed.add_field(
        name="✅ For",
        value=f"{positive_votes} ({for_percentage:.1f}%)",
        inline=True
    )

    embed.add_field(
        name="❌ Against",
        value=f"{negative_votes} ({100-for_percentage:.1f}%)",
        inline=True
    )

    embed.add_field(
        name="📈 Required",
        value=f"{required_percentage*100:.0f}%",
        inline=True
    )

    if proposer_name:
        embed.set_footer(text=f"Proposed by {proposer_name}")

    return embed

def create_election_announcement_embed(
    guild: discord.Guild,
    start_time: datetime,
    end_time: datetime
) -> discord.Embed:
    embed = discord.Embed(
        title="📢 Election Announcement",
        description=f"**Attention citizens of {guild.name}!**\n\n"
                    f"Elections for the Grand Council are approaching! This is your opportunity to shape "
                    f"the future of our community by running for office or voting for your preferred candidates.\n\n"
                    f"**Campaign Period:** Now until voting begins\n"
                    f"**Voting Period:** <t:{int(start_time.timestamp())}:F> to <t:{int(end_time.timestamp())}:F>",
        color=0x3498DB
    )

    embed.add_field(
        name="🚀 How to Participate",
        value="• **Register to Vote**: Click the 🗳️ button below\n"
              "• **Run for Office**: Click the 🚀 button to become a candidate\n"
              "• **Campaign**: Share your vision with the community!",
        inline=False
    )

    embed.add_field(
        name="📜 Requirements",
        value="• Must be a server member for at least 1 month\n"
              "• Maximum 9 candidates per election\n"
              "• Anonymous voting system",
        inline=False
    )

    embed.set_footer(text="Democracy in action! 🗳️")
    return embed

def create_ministerial_appointment_embed(
    member: discord.Member,
    position: str,
    appointed_by: discord.Member,
    is_removal: bool = False
) -> discord.Embed:
    if is_removal:
        embed = discord.Embed(
            title="🏛️ Ministerial Change",
            description=f"**{member.mention}** has been removed from the position of **{position}**",
            color=0xE74C3C
        )
    else:
        embed = discord.Embed(
            title="🏛️ Ministerial Appointment",
            description=f"**{member.mention}** has been appointed as **{position}**",
            color=0xF39C12
        )

    embed.add_field(
        name="Appointed By",
        value=appointed_by.mention,
        inline=True
    )

    if member.avatar:
        embed.set_thumbnail(url=member.avatar.url)

    return embed

def create_emergency_embed(
    title: str,
    description: str,
    president: discord.Member,
    additional_fields: Optional[dict] = None
) -> discord.Embed:
    embed = discord.Embed(
        title=f"🚨 {title}",
        description=description,
        color=0xE74C3C
    )

    embed.add_field(
        name="🎖️ Declared By",
        value=president.mention,
        inline=True
    )

    if additional_fields:
        for name, value in additional_fields.items():
            embed.add_field(name=name, value=value, inline=False)

    embed.set_footer(text="⚠️ Emergency powers in effect - Constitution Article 7")
    return embed

