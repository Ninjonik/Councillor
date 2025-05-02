import discord
from discord.ext import commands
from discord import app_commands
import presets


class Manage(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client

    @app_commands.command(name='suggest', description="Creates a Council Proposal for MPs to vote!")
    @app_commands.choices(voting_type=[
        app_commands.Choice(name="⚖️ Legislation", value="legislation"),
        app_commands.Choice(name="🔵 Amendment", value="amendment"),
        app_commands.Choice(name="🛑 Decree", value="decree"),
    ])
    async def manage(self, interaction: discord.Interaction, title: str, description: str,
                               voting_type: app_commands.Choice[str]):
        try:
            eligible = await presets.is_eligible(interaction.user, interaction.guild, "councillor")

            if not eligible:
                await presets.handle_interaction_error(
                    interaction, 
                    custom_message="❌ **Not Eligible!** You are not a Councillor of this server.",
                    ephemeral=True
                )
                return

            await presets.create_new_voting(self.client, title, description, interaction.user, interaction.guild,
                                            voting_type.value, "voting")
            await interaction.response.send_message("✅ **Success!** Your proposal has been successfully posted!")
        except Exception as e:
            await presets.handle_interaction_error(
                interaction, 
                e, 
                "❌ **Error!** There was an error while creating your proposal."
            )


async def setup(client: commands.Bot) -> None:
    await client.add_cog(Manage(client))
