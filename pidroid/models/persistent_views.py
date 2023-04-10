import discord
import logging

from pidroid.constants import JUSTANYONE_ID

logger = logging.getLogger('Pidroid')

class PersistentSuggestionDeletionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Remove', style=discord.ButtonStyle.red, custom_id='persistent_suggestion_deletion_view:delete_button')
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.message is None:
            return await interaction.response.send_message('Associated message could not be found', ephemeral=True)
        await interaction.message.delete(delay=0)
        await interaction.response.defer()
        

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        """Called when view catches an error."""
        logger.exception(error)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure that the interaction is called by a user authorized to delete suggestions.

        JustAnyone, in this case."""
        if interaction.user and interaction.user.id == JUSTANYONE_ID:
            return True
        await interaction.response.send_message('This menu cannot be controlled by you!', ephemeral=True)
        return False
