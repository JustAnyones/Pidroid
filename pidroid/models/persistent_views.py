import discord
import logging

from discord import Member, Message, TextChannel, Interaction

from pidroid.utils.checks import TheoTownChecks, is_guild_theotown, member_has_channel_permission
from pidroid.utils.time import utcnow

logger = logging.getLogger('Pidroid')

class PersistentSuggestionManagementView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @staticmethod
    def get_thread_from_message(message: Message):
        channel = message.channel
        assert isinstance(channel, discord.TextChannel)
        return channel.get_thread(message.id) # the thread starter message ID is the same ID as the thread

    @staticmethod
    async def close_suggestion(message: Message, responsible_user: str, reason: str):
        # Get the thread for the suggestion
        thread = PersistentSuggestionManagementView.get_thread_from_message(message)

        # Update the original suggestion message to remove reactions
        embed = message.embeds[0]

        liked = hated = 0
        for reaction in message.reactions:
            if reaction.emoji == "✅":
                liked = reaction.count - 1
            elif reaction.emoji == "❌":
                hated = reaction.count - 1

        embed.set_footer(
            text=f"{liked} people liked the idea, {hated} hated the idea | Marked as {message}"
        )
        await message.edit(embed=embed)
        # TODO: remove reactions


        # Lock the suggestion thread, if available
        if thread:
            await thread.send(f"{responsible_user} marked this suggestion as {reason}")
            await thread.edit(locked=True)

    @discord.ui.button(
        label='Mark as completed',
        style=discord.ButtonStyle.green,
        custom_id='persistent_suggestion_management_view:mark_as_completed_button'
    )
    async def mark_as_completed_button(self, interaction: Interaction, button: discord.ui.Button):
        if interaction.message is None:
            return await interaction.response.send_message('Associated message could not be found', ephemeral=True)
        
        await PersistentSuggestionManagementView.close_suggestion(
            interaction.message, str(interaction.user), "completed"
        )
        await interaction.response.defer()

    @discord.ui.button(
        label='Remove',
        style=discord.ButtonStyle.red,
        custom_id='persistent_suggestion_deletion_view:delete_button'
    )
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.message is None:
            return await interaction.response.send_message('Associated message could not be found', ephemeral=True)
        
        thread = PersistentSuggestionManagementView.get_thread_from_message(interaction.message)

        await interaction.message.delete(delay=0)

        if thread:
            await thread.delete()
        await interaction.response.defer()
        

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        """Called when view catches an error."""
        logger.exception(error)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure that the interaction is called by a user authorized to delete suggestions.

        JustAnyone or the suggestion author, in this case."""

        # If I cannot locate the message, the interaction check fails
        if interaction.message is None:
            await interaction.response.send_message('Associated message could not be found', ephemeral=True)
            return False

        assert isinstance(interaction.message.channel, TextChannel)

        # If user who interacted in TheoTown guild is a developer
        if is_guild_theotown(interaction.message.guild):
            if TheoTownChecks.is_developer(interaction.user):
                return True
            
        # If it is not TheoTown guild, check if member has manage_messages permission
        elif (
            isinstance(interaction.user, Member)
            and member_has_channel_permission(interaction.message.channel, interaction.user, 'manage_messages')
        ):
            return True

        icon_url = interaction.message.embeds[0].author.icon_url
        author_id_from_icon = None
        if icon_url:
            try:
                split = icon_url.split('https://cdn.discordapp.com/avatars/')[1].split('/')[0]
                author_id_from_icon = int(split)
            except Exception:
                author_id_from_icon = None

        # If it's the message author
        if author_id_from_icon and author_id_from_icon == interaction.user.id:

            if utcnow().timestamp() - interaction.message.created_at.timestamp() <= 5*60:
                return True
            await interaction.response.send_message(
                'Suggestion can only be deleted within 5 minutes of sending it.',
                ephemeral=True
            )
            return False

        # Otherwise, say no
        await interaction.response.send_message("You are not authorized to remove the suggestions here.", ephemeral=True)
        return False
