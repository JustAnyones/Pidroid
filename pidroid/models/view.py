import discord
import logging

from contextlib import suppress
from discord import Colour, Interaction, NotFound
from discord.ext.commands import Context
from discord.ui import Item, View
from typing import TYPE_CHECKING, Optional

from pidroid.utils.embeds import PidroidEmbed
from pidroid.utils.paginators import PageSource

if TYPE_CHECKING:
    from pidroid.client import Pidroid

logger = logging.getLogger("Pidroid")

class BaseView(View):

    def __init__(self, client: Pidroid, ctx: Context, *, timeout: float = 600):
        super().__init__(timeout=timeout)
        self._client = client
        self._ctx = ctx
        self._embed = PidroidEmbed()
        self._check_embed_permissions = False
        self.clear_items()

    async def send(self):
        """Sends the message with the view."""
        if self._check_embed_permissions and not self._ctx.channel.permissions_for(self._ctx.me).embed_links:
            return await self._ctx.reply("Bot does not have embed links permission in this channel.")

        self._message = await self._ctx.reply(embed=self._embed, view=self)

    async def close_view(self, interaction: Interaction) -> None:
        """Called to clean up when the view is closed by the user."""
        if self._message:
            await self._message.delete()
        await interaction.response.send_message("Menu has been closed.", ephemeral=True)
        self.stop()

    async def timeout_view(self, interaction: Optional[Interaction]) -> None:
        """Called to clean up when the interaction or view timed out."""
        self._embed.set_footer(text="Menu has timed out.")
        self._embed.colour = Colour.red()
        await self.finish_interface(interaction)

    async def finish_interface(
        self,
        interaction: Optional[Interaction],
        embed: Optional[PidroidEmbed] = None
    ) -> None:
        """Removes all buttons and updates the view. No more calls can be done to the view."""
        # Remove all items
        for child in self.children.copy():
            self.remove_item(child)

        # If embed is provided, update it
        if embed:
            self._embed = embed
        await self._update_view(interaction) # Update message with latest information
        self.stop() # Stop responding to any interaction

    async def _update_view(self, interaction: Optional[Interaction]) -> None:
        """Updates the original interaction response message.
        
        If interaction object is not provided, then the message itself will be edited."""
        if interaction is None:
            with suppress(NotFound):
                await self._message.edit(embed=self._embed, view=self)
        else:
            await interaction.response.edit_message(embed=self._embed, view=self)

    """Event listeners"""

    async def on_timeout(self) -> None:
        """Called when view times out."""
        await self.timeout_view(None)

    async def on_error(self, interaction: Interaction, error: Exception, item: Item) -> None:
        """Called when view catches an error."""
        logger.exception(error)
        logger.error(f"The above exception is caused by {str(item)} item")
        message = "An unknown error was encountered"
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    async def interaction_check(self, interaction: Interaction) -> bool:
        """Ensure that the interaction is called by the message author."""
        if interaction.user and interaction.user.id == self._ctx.author.id:
            return True
        await interaction.response.send_message("This menu cannot be controlled by you!", ephemeral=True)
        return False
    
    @discord.ui.button(label="Close", style=discord.ButtonStyle.red, row=2)
    async def close_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        """Closes the view."""
        await self.close_view(interaction)

class PaginatingView(BaseView):
    
    def __init__(
        self,
        client: Pidroid,
        ctx: Context,
        *,
        timeout: float = 600,
        source: Optional[PageSource] = None
    ):
        super().__init__(client, ctx, timeout=timeout)
        self.set_source(source)

    @property
    def source(self) -> PageSource:
        """Returns the pagination source of the view, if it was set.
        
        Raises NotImplementedError if it is not set. This only happens
        if source was not set in the constructor."""
        if self._source:
            return self._source
        raise NotImplementedError

    def set_source(self, source: Optional[PageSource]):
        """Sets the paginator source.
        
        It is automatically called in the constructor if source is provided.
        
        You can call it yourself."""
        self._current_page = 0
        self._source = source
        if source:
            self.clear_items()
            if self.source.is_paginating():
                self.add_pagination_buttons()

    async def initialize_paginator(self):
        """Should be called after setting the source to initialize the paginator
        
        before sending it to the user."""
        await self.source._prepare_once()
        page = await self.source.get_page(0)
        self._embed = await self._get_embed_from_page(page)
        self._update_labels(0)
    
    def add_pagination_buttons(self, *, close_button: bool = True):
        """Adds the pagination buttons to the view in the first row."""
        max_pages = self.source.get_max_pages()
        use_last_and_first = max_pages is not None and max_pages >= 2
        if use_last_and_first:
            self.add_item(self.go_to_first_page)  # type: ignore
        self.add_item(self.go_to_previous_page)  # type: ignore
        self.add_item(self.go_to_current_page)  # type: ignore
        self.add_item(self.go_to_next_page)  # type: ignore
        if use_last_and_first:
            self.add_item(self.go_to_last_page)  # type: ignore
        if close_button:
            self.add_item(self.close_button)  # type: ignore

    async def send(self):
        if self._source is not None:
            await self.initialize_paginator()
        return await super().send()

    async def _get_embed_from_page(self, page: int) -> discord.Embed: # type: ignore
        value = await discord.utils.maybe_coroutine(self.source.format_page, self, page) # type: ignore
        return value

    async def show_page(self, interaction: discord.Interaction, page_number: int) -> None:
        page = await self.source.get_page(page_number)
        self._current_page = page_number
        embed = await self._get_embed_from_page(page)
        self._update_labels(page_number)
        if embed:
            if interaction.response.is_done():
                if self._message:
                    await self._message.edit(embed=embed, view=self)
            else:
                await interaction.response.edit_message(embed=embed, view=self)

    def _update_labels(self, page_number: int) -> None:
        self.go_to_current_page.label = f"{page_number + 1}/{self.source.get_max_pages()}"
        self.go_to_next_page.disabled = False
        self.go_to_previous_page.disabled = False

        max_pages = self.source.get_max_pages()
        if max_pages is not None:
            if (page_number + 1) >= max_pages:
                self.go_to_next_page.disabled = True
            if page_number == 0:
                self.go_to_previous_page.disabled = True

    async def show_checked_page(self, interaction: discord.Interaction, page_number: int) -> None:
        max_pages = self.source.get_max_pages()
        try:
            if max_pages is None:
                # If it doesn't give maximum pages, it cannot be checked
                await self.show_page(interaction, page_number)
            elif max_pages > page_number >= 0:
                await self.show_page(interaction, page_number)
        except IndexError:
            # An error happened that can be handled, so ignore it.
            pass

    @discord.ui.button(label='≪', style=discord.ButtonStyle.grey)
    async def go_to_first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """go to the first page"""
        await self.show_page(interaction, 0)

    @discord.ui.button(label='Back', style=discord.ButtonStyle.grey)
    async def go_to_previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """go to the previous page"""
        await self.show_checked_page(interaction, self._current_page - 1)

    @discord.ui.button(label='Current', style=discord.ButtonStyle.grey, disabled=True)
    async def go_to_current_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label='Next', style=discord.ButtonStyle.grey)
    async def go_to_next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """go to the next page"""
        await self.show_checked_page(interaction, self._current_page + 1)

    @discord.ui.button(label='≫', style=discord.ButtonStyle.grey)
    async def go_to_last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """go to the last page"""
        # The call here is safe because it's guarded by skip_if
        await self.show_page(interaction, self.source.get_max_pages() - 1)
