import datetime

import discord
import discord.utils
from discord.ext import tasks, commands
from discord import app_commands

import config
import presets


class Council(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client

    @app_commands.command(name="council", description="Become a MP or learn about Grand Council!")
    async def council(self, interaction: discord.Interaction):
        member = interaction.user
        embed = discord.Embed(
            title=f"**The Grand Council**",
            description="**The Grand Council** is a group of members (MPs) who have the right to vote on proposed "
                        "changes to the "
                        f"{interaction.guild.name} server. These changes are put forward by the Chancellor, "
                        "who is also responsible for guiding the direction of the Grand Council and the server. MPs "
                        "also have the ability to propose new laws to the Chancellor for future consideration.",
            colour=discord.Colour.green()
        )
        embed.set_thumbnail(url=member.guild.icon)
        embed.add_field(
            name="**Become MP**",
            value='Click on the "Become MP!" button in order to become a MP yourself!',
            inline=True,
        )
        embed.add_field(
            name="What is the Grand Council?",
            value='Click on the "The Grand Council" button to check what is the Grand Council about and '
                  'what it can do!',
            inline=True,
        )

        role = '❌'
        req_role = interaction.guild.get_role(config.ROLE_REQUIREMENT_ID)
        if not req_role or (req_role and req_role in interaction.user.roles):
            role = '✅'

        joined_at = member.joined_at
        current_time_utc = datetime.datetime.now(datetime.timezone.utc)
        joined_at_days = (current_time_utc - joined_at).days

        joined = '✅'
        if joined_at_days < config.DAYS_REQUIREMENT:
            joined = '❌'

        embed.add_field(
            name="**Requirements for MP**",
            value='To become a MP you need to pass the following criteria:\n'
                  f'1. Be a member of the server for 6+ months {joined}\n'
                  f'2. Have no major punishments during the last 6 months. ❓\n'
                  f'3. Have the Valued Citizen role. {role}\n',
            inline=False,
        )

        await interaction.response.send_message(content=f"{member.mention}", embed=embed, ephemeral=True,
                                                view=presets.CouncilDialog(self.client))


async def setup(client: commands.Bot) -> None:
    await client.add_cog(Council(client))
