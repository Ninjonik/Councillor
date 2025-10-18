import discord
from datetime import datetime
import utils

def create_success_embed(title: str, description: str) -> discord.Embed:
    embed = discord.Embed(title=f"✅ {title}", description=description, color=0x2ECC71)
    embed.timestamp = utils.datetime_now()
    return embed

def create_error_embed(title: str, description: str) -> discord.Embed:
    embed = discord.Embed(title=f"❌ {title}", description=description, color=0xE74C3C)
    embed.timestamp = utils.datetime_now()
    return embed

def create_info_embed(title: str, description: str) -> discord.Embed:
    embed = discord.Embed(title=f"ℹ️ {title}", description=description, color=0x3498DB)
    embed.timestamp = utils.datetime_now()
    return embed

def create_election_announcement_embed(guild: discord.Guild, start_time: datetime, end_time: datetime) -> discord.Embed:
    """Create embed for election announcement"""
    embed = discord.Embed(
        title="📢 Grand Council Elections Announced!",
        description=f"**Welcome, citizens of {guild.name}!**\n\n"
                    f"Elections for the Grand Council have been announced. "
                    f"This is your opportunity to serve your community or vote for new leadership.\n\n"
                    f"## 🗳️ Election Timeline\n"
                    f"### 📝 **Registration Period:** Now until voting begins\n"
                    f"### 🗳️ **Voting Period:** <t:{int(start_time.timestamp())}:F> to <t:{int(end_time.timestamp())}:F>\n\n"
                    f"**How to Participate:**\n"
                    f"• Click '🏛️ Run for Council' below to register as a candidate\n"
                    f"• Click '✅ Register to Vote' below to register as a voter\n"
                    f"• You must have been a member for at least 30 days to vote\n"
                    f"• Maximum of 9 candidates can run per election",
        colour=0xF39C12,
        timestamp=utils.datetime_now()
    )
    embed.set_footer(text="Grand Council Elections • Registration is now open")
    return embed

def create_voting_embed(guild: discord.Guild, election: dict, candidates: list, voters: list) -> discord.Embed:
    """Create embed for voting phase"""
    embed = discord.Embed(
        title="🗳️ Grand Council Elections - Voting Now Open",
        description=f"**Welcome, citizens of {guild.name}!**\n\n"
                    f"The voting period has begun for new Grand Council members. "
                    f"Please review the candidates below and cast your vote.\n\n"
                    f"**{len(candidates)} candidate{'s' if len(candidates) != 1 else ''}** • "
                    f"**{len(voters)} registered voter{'s' if len(voters) != 1 else ''}**\n\n"
                    f"⏰ **Voting Period**\n"
                    f"From <t:{int(datetime.fromisoformat(election['voting_start']).timestamp())}:F>\n"
                    f"To <t:{int(datetime.fromisoformat(election['voting_end']).timestamp())}:F>",
        colour=0x3498DB,
        timestamp=utils.datetime_now()
    )

    for i, candidate in enumerate(candidates):
        emoji = utils.generate_keycap_emoji(i + 1)
        embed.add_field(
            name=f"{emoji} {candidate['name']}",
            value="Running for Council seat",
            inline=True
        )

    embed.set_footer(text="Click a button below to cast your vote • You can vote for up to 2 candidates")
    return embed

def create_results_embed(guild: discord.Guild, winners: list) -> discord.Embed:
    """Create embed for election results"""
    embed = discord.Embed(
        title="🏆 Grand Council Election Results",
        description=f"**Attention, citizens of {guild.name}!**\n\n"
                    f"The election has concluded. Here are your newly elected Grand Council members:",
        colour=0x2ECC71,
        timestamp=utils.datetime_now()
    )

    for i, winner in enumerate(winners):
        emoji = utils.generate_keycap_emoji(i + 1)
        vote_text = f"{winner['votes']} vote{'s' if winner['votes'] != 1 else ''}"
        embed.add_field(
            name=f"{emoji} {winner['name']}",
            value=f"✅ Elected with {vote_text}",
            inline=False
        )

    embed.set_footer(text="Congratulations to the winners! 🎉")
    return embed

def create_voting_proposal_embed(title: str, description: str, voting_type_data: dict, author: discord.Member, voting_end: datetime, voting_id: str = None) -> discord.Embed:
    """Create embed for a voting proposal"""
    embed = discord.Embed(
        title=f"{voting_type_data['emoji']} {voting_type_data['name']}",
        description=f"## {title}\n\n{description}\n\n"
                    f"### 📊 Voting Information\n"
                    f"**Proposed by:** {author.mention}\n"
                    f"**Voting Ends:** <t:{int(voting_end.timestamp())}:R> (<t:{int(voting_end.timestamp())}:F>)\n"
                    f"**Required Approval:** {int(voting_type_data['required_percentage'] * 100)}%\n\n"
                    f"### 🗳️ How to Vote\n"
                    f"Click the buttons below to cast your vote. Your vote is **anonymous** and can only be cast once.",
        color=0x3498DB,
        timestamp=utils.datetime_now()
    )

    footer_text = f"Vote Type: {voting_type_data['description']}"
    if voting_id:
        footer_text += f" • ID: {voting_id}"
    embed.set_footer(text=footer_text)

    return embed

def create_voting_result_embed(title: str, description: str, passed: bool, votes_for: int, votes_against: int, required_percentage: float, proposer_name: str = None) -> discord.Embed:
    """Create embed for voting results"""
    total_votes = votes_for + votes_against
    percentage = (votes_for / total_votes * 100) if total_votes > 0 else 0

    embed = discord.Embed(
        title=f"{'✅ Proposal Passed' if passed else '❌ Proposal Failed'}",
        description=f"**{title}**\n\n{description[:200]}...",
        color=0x2ECC71 if passed else 0xE74C3C,
        timestamp=utils.datetime_now()
    )

    embed.add_field(name="✅ For", value=str(votes_for), inline=True)
    embed.add_field(name="❌ Against", value=str(votes_against), inline=True)
    embed.add_field(name="📊 Total", value=str(total_votes), inline=True)

    embed.add_field(
        name="📈 Result",
        value=f"{percentage:.1f}% approval (needed {int(required_percentage * 100)}%)",
        inline=False
    )

    if proposer_name:
        embed.set_footer(text=f"Proposed by {proposer_name}")

    return embed

def create_council_info_embed(guild: discord.Guild, chancellor: str, council_members: list) -> discord.Embed:
    """Create embed for council information"""
    embed = discord.Embed(
        title=f"🏛️ {guild.name} Grand Council",
        description="Current members of the Grand Council and leadership",
        color=0x3498DB,
        timestamp=utils.datetime_now()
    )

    embed.add_field(
        name="👑 Chancellor",
        value=chancellor if chancellor else "*None appointed*",
        inline=False
    )

    if council_members:
        embed.add_field(
            name=f"🎖️ Council Members ({len(council_members)})",
            value="\n".join(council_members) if len(council_members) <= 25 else "\n".join(council_members[:25]) + f"\n*...and {len(council_members) - 25} more*",
            inline=False
        )
    else:
        embed.add_field(
            name="🎖️ Council Members",
            value="*No members elected*",
            inline=False
        )

    embed.set_footer(text="Grand Council of " + guild.name)
    return embed

def create_ministry_list_embed(guild: discord.Guild, ministries: list) -> discord.Embed:
    """Create embed for ministry list"""
    embed = discord.Embed(
        title=f"🏛️ {guild.name} Ministries",
        description="Current ministries and their leadership",
        color=0x9B59B6,
        timestamp=utils.datetime_now()
    )

    if not ministries:
        embed.description = "No ministries have been created yet."
        return embed

    for ministry in ministries:
        minister = f"<@{ministry['minister_id']}>" if ministry.get('minister_id') else "*Vacant*"
        deputy = f"<@{ministry['deputy_minister_id']}>" if ministry.get('deputy_minister_id') else "*Vacant*"
        role = f"<@&{ministry['role_id']}>" if ministry.get('role_id') else "*No role*"

        value = f"**Minister:** {minister}\n**Deputy:** {deputy}\n**Role:** {role}"

        embed.add_field(
            name=f"📁 {ministry['name']}",
            value=value,
            inline=False
        )

    embed.set_footer(text=f"Total Ministries: {len(ministries)}")
    return embed

# Legacy compatibility
def success_embed(title: str, description: str) -> discord.Embed:
    return create_success_embed(title, description)

def error_embed(title: str, description: str) -> discord.Embed:
    return create_error_embed(title, description)

def info_embed(title: str, description: str) -> discord.Embed:
    return create_info_embed(title, description)
