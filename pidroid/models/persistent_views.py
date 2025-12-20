import discord
import logging

from discord import Member, Message, TextChannel, Interaction
from discord.ui import View, Button, TextInput
from typing import override

from pidroid.models.view import PidroidModal
from pidroid.utils.checks import TheoTownChecks, is_guild_theotown, member_has_channel_permission
from pidroid.utils.time import utcnow

logger = logging.getLogger('pidroid.persistent_views')

MAX_REASON_LENGTH = 512

def user_id_from_icon_url(icon_url: str) -> int | None:
    """Extracts user ID from a Discord avatar URL, if possible."""
    try:
        split = icon_url.split('https://cdn.discordapp.com/avatars/')[1].split('/')[0]
        return int(split)
    except Exception:
        return None

class SuggestionMarkContextModal(PidroidModal, title='Provide reason for closing'):
    reason_input: TextInput[View] = TextInput(
        label="Reason",
        placeholder="Please provide the reason you are closing this suggestion.",
        max_length=MAX_REASON_LENGTH,
        required=True,
        style=discord.TextStyle.paragraph
    )

class PersistentSuggestionManagementView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @staticmethod
    def get_thread_from_message(message: Message):
        channel = message.channel
        assert isinstance(channel, TextChannel)
        return channel.get_thread(message.id) # the thread starter message ID is the same ID as the thread

    @staticmethod
    async def close_suggestion(message: Message, responsible_user: str, reason: str):
        # Get the thread for the suggestion
        thread = PersistentSuggestionManagementView.get_thread_from_message(message)

        # Update the original suggestion message to remove reactions
        embed = message.embeds[0]

        liked = hated = 0
        message = await message.channel.fetch_message(message.id)
        for reaction in message.reactions:
            if reaction.emoji == "✅":
                liked = reaction.count - 1
            elif reaction.emoji == "❌":
                hated = reaction.count - 1

        _ = embed.set_footer(
            text=f"{liked} user(s) liked the idea, {hated} hated the idea | Closed by {responsible_user}"
        )
        _ = await message.edit(embed=embed, view=None)
        await message.clear_reactions()

        icon_url = embed.author.icon_url
        author_id = None
        if icon_url:
            author_id = user_id_from_icon_url(icon_url)

        # Lock the suggestion thread, if available
        if thread:
            users_to_mention: list[str] = []
            if author_id:
                users_to_mention.append(f"<@{author_id}>")

            _ = await thread.send(
                f":lock: {responsible_user} closed this for the following reason:\n{reason}\n{' '.join(users_to_mention)}",
                allowed_mentions=discord.AllowedMentions(users=True)
            )
            _ = await thread.edit(locked=True)

    @discord.ui.button(
        label='Close...',
        style=discord.ButtonStyle.gray,
        custom_id='persistent_suggestion_management_view:mark_as_completed_button'
    )
    async def mark_as_completed_button(self, interaction: Interaction, button: Button[View]):
        if not await self.check_permissions(interaction, button):
            return

        if interaction.message is None:
            return await interaction.response.send_message('Associated message could not be found', ephemeral=True)
        
        message = interaction.message

        modal = SuggestionMarkContextModal()
        await interaction.response.send_modal(modal)
        timed_out = await modal.wait()
        if timed_out:
            return await interaction.response.send_message(f"Modal timed out, you typed:\n{modal.reason_input.value}", ephemeral=True)

        interaction = modal.interaction
        value = modal.reason_input.value
        if len(value) > MAX_REASON_LENGTH:
            return await interaction.response.send_message(f"Keep the reason up within {MAX_REASON_LENGTH} characters.", ephemeral=True)

        await PersistentSuggestionManagementView.close_suggestion(
            message, str(interaction.user), value
        )

    @discord.ui.button(
        label='Remove',
        style=discord.ButtonStyle.red,
        custom_id='persistent_suggestion_deletion_view:delete_button'
    )
    async def delete_button(self, interaction: discord.Interaction, button: Button[View]):
        if not await self.check_permissions(interaction, button):
            return

        if interaction.message is None:
            return await interaction.response.send_message('Associated message could not be found', ephemeral=True)
        
        thread = PersistentSuggestionManagementView.get_thread_from_message(interaction.message)

        await interaction.message.delete(delay=0)

        if thread:
            await thread.delete()
        await interaction.response.defer()
        
    @override
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item[View]) -> None:
        """Called when view catches an error."""
        logger.exception(error)

    async def check_permissions(self, interaction: discord.Interaction, item: discord.ui.Item[View]) -> bool:
        # If I cannot locate the message, the permission check fails
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
        
        # If it's sent by the author, but it's not deletion
        if isinstance(item, Button):
            if item.custom_id != "persistent_suggestion_deletion_view:delete_button":
                await interaction.response.send_message("You are not authorized to perform this operation here.", ephemeral=True)
                return False

        icon_url = interaction.message.embeds[0].author.icon_url
        author_id_from_icon = None
        if icon_url:
            author_id_from_icon = user_id_from_icon_url(icon_url)

        # If it's the message author
        if author_id_from_icon and author_id_from_icon == interaction.user.id:

            if utcnow().timestamp() - interaction.message.created_at.timestamp() <= 10*60:
                return True
            await interaction.response.send_message(
                'Suggestion can only be deleted within 10 minutes of sending it.',
                ephemeral=True
            )
            return False

        # Otherwise, say no
        await interaction.response.send_message("You are not authorized to perform this operation here.", ephemeral=True)
        return False

    @override
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure that the interaction is called for a manageable message.
        
        The actual permission checking occurs in check_permissions and should be called by every callback."""

        # If I cannot locate the message, the interaction check fails
        if interaction.message is None:
            await interaction.response.send_message('Associated message could not be found', ephemeral=True)
            return False
        return True
