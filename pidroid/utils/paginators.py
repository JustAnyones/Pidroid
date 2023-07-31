"""
The MIT License (MIT)

Copyright (c) 2015-2019 Rapptz & JustAnyone

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.

https://github.com/Rapptz/discord-ext-menus/commits/fbb8803779373357e274e1540b368365fd9d8074/discord/ext/menus/__init__.py
"""

import asyncio
import discord

from contextlib import suppress
from discord.errors import NotFound
from discord.ext import commands
from discord.utils import format_dt
from typing import TYPE_CHECKING, List, Optional, Dict, Any

from pidroid.models.plugins import Plugin
from pidroid.models.punishments import Case
from pidroid.utils.embeds import PidroidEmbed

if TYPE_CHECKING:
    from pidroid.client import Pidroid

class PageSource:
    """An interface representing a menu page's data source for the actual menu page.

    Subclasses must implement the backing resource along with the following methods:

    - :meth:`get_page`
    - :meth:`is_paginating`
    - :meth:`format_page`
    """
    async def _prepare_once(self):
        try:
            # Don't feel like formatting hasattr with
            # the proper mangling
            # read this as follows:
            # if hasattr(self, '__prepare')
            # except that it works as you expect
            self.__prepare
        except AttributeError:
            await self.prepare()
            self.__prepare = True

    async def prepare(self):
        """|coro|

        A coroutine that is called after initialisation
        but before anything else to do some asynchronous set up
        as well as the one provided in ``__init__``.

        By default this does nothing.

        This coroutine will only be called once.
        """
        return

    def is_paginating(self):
        """An abstract method that notifies the :class:`MenuPages` whether or not
        to start paginating. This signals whether to add reactions or not.

        Subclasses must implement this.

        Returns
        --------
        :class:`bool`
            Whether to trigger pagination.
        """
        raise NotImplementedError

    def get_max_pages(self):
        """An optional abstract method that retrieves the maximum number of pages
        this page source has. Useful for UX purposes.

        The default implementation returns ``None``.

        Returns
        --------
        Optional[:class:`int`]
            The maximum number of pages required to properly
            paginate the elements, if given.
        """
        return None

    async def get_page(self, page_number):
        """|coro|

        An abstract method that retrieves an object representing the object to format.

        Subclasses must implement this.

        .. note::

            The page_number is zero-indexed between [0, :meth:`get_max_pages`),
            if there is a maximum number of pages.

        Parameters
        -----------
        page_number: :class:`int`
            The page number to access.

        Returns
        ---------
        Any
            The object represented by that page.
            This is passed into :meth:`format_page`.
        """
        raise NotImplementedError

    async def format_page(self, menu, page):
        """|maybecoro|

        An abstract method to format the page.

        This method must return one of the following types.

        If this method returns a ``str`` then it is interpreted as returning
        the ``content`` keyword argument in :meth:`discord.Message.edit`
        and :meth:`discord.abc.Messageable.send`.

        If this method returns a :class:`discord.Embed` then it is interpreted
        as returning the ``embed`` keyword argument in :meth:`discord.Message.edit`
        and :meth:`discord.abc.Messageable.send`.

        If this method returns a ``dict`` then it is interpreted as the
        keyword-arguments that are used in both :meth:`discord.Message.edit`
        and :meth:`discord.abc.Messageable.send`. The two of interest are
        ``embed`` and ``content``.

        Parameters
        ------------
        menu: :class:`Menu`
            The menu that wants to format this page.
        page: Any
            The page returned by :meth:`PageSource.get_page`.

        Returns
        ---------
        Union[:class:`str`, :class:`discord.Embed`, :class:`dict`]
            See above.
        """
        raise NotImplementedError

class ListPageSource(PageSource):
    """A data source for a sequence of items.

    This page source does not handle any sort of formatting, leaving it up
    to the user. To do so, implement the :meth:`format_page` method.

    Attributes
    ------------
    entries: Sequence[Any]
        The sequence of items to paginate.
    per_page: :class:`int`
        How many elements are in a page.
    """

    def __init__(self, entries, *, per_page):
        self.entries = entries
        self.per_page = per_page

        pages, left_over = divmod(len(entries), per_page)
        if left_over:
            pages += 1

        self._max_pages = pages

    def is_paginating(self):
        """:class:`bool`: Whether pagination is required."""
        return len(self.entries) > self.per_page

    def get_max_pages(self):
        """:class:`int`: The maximum number of pages required to paginate this sequence."""
        return self._max_pages

    async def get_page(self, page_number):
        """Returns either a single element of the sequence or
        a slice of the sequence.

        If :attr:`per_page` is set to ``1`` then this returns a single
        element. Otherwise it returns at most :attr:`per_page` elements.

        Returns
        ---------
        Union[Any, List[Any]]
            The data returned.
        """
        if self.per_page == 1:
            return self.entries[page_number]
        else:
            base = page_number * self.per_page
            return self.entries[base:base + self.per_page]

# This is based on the work done here: https://github.com/Rapptz/RoboDanny/commit/ff6217d80d1ac960bf75431f67bf07eb610006f8
class PidroidPages(discord.ui.View):
    def __init__(
        self,
        source: PageSource,
        *,
        ctx: commands.Context, # type: ignore
        check_embeds: bool = True,
    ):
        super().__init__()
        self.source: PageSource = source
        self.check_embeds: bool = check_embeds
        self.ctx: commands.Context = ctx # type: ignore
        self.message: Optional[discord.Message] = None
        self.current_page: int = 0
        self.input_lock = asyncio.Lock()

        self.clear_items()
        if source.is_paginating():
            max_pages = source.get_max_pages()
            use_last_and_first = max_pages is not None and max_pages >= 2
            if use_last_and_first:
                self.add_item(self.go_to_first_page)  # type: ignore
            self.add_item(self.go_to_previous_page)  # type: ignore
            self.add_item(self.go_to_current_page)  # type: ignore
            self.add_item(self.go_to_next_page)  # type: ignore
            if use_last_and_first:
                self.add_item(self.go_to_last_page)  # type: ignore
            self.add_item(self.stop_pages)  # type: ignore

    async def _get_kwargs_from_page(self, page: int) -> Optional[Dict[str, Any]]: # type: ignore
        value = await discord.utils.maybe_coroutine(self.source.format_page, self, page) # type: ignore
        if isinstance(value, dict):
            return value
        elif isinstance(value, str):
            return {'content': value, 'embed': None}
        elif isinstance(value, discord.Embed):
            return {'embed': value, 'content': None}

    async def show_page(self, interaction: discord.Interaction, page_number: int) -> None:
        page = await self.source.get_page(page_number)
        self.current_page = page_number
        kwargs = await self._get_kwargs_from_page(page)
        self._update_labels(page_number)
        if kwargs:
            if interaction.response.is_done():
                if self.message:
                    await self.message.edit(**kwargs, view=self)
            else:
                await interaction.response.edit_message(**kwargs, view=self)

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

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user and interaction.user.id in (self.ctx.bot.owner_id, self.ctx.author.id):
            return True
        await interaction.response.send_message('This pagination menu cannot be controlled by you, sorry!', ephemeral=True)
        return False

    async def on_timeout(self) -> None:
        if self.message:
            with suppress(NotFound):
                await self.message.edit(view=None)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        assert isinstance(self.ctx.bot, Pidroid)
        self.ctx.bot.logger.exception(error)
        if interaction.response.is_done():
            await interaction.followup.send('An unknown error occurred, sorry', ephemeral=True)
        else:
            await interaction.response.send_message('An unknown error occurred, sorry', ephemeral=True)

    async def start(self):
        if self.check_embeds and not self.ctx.channel.permissions_for(self.ctx.me).embed_links:
            return await self.ctx.reply('Bot does not have embed links permission in this channel.')

        await self.source._prepare_once()
        page = await self.source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)
        self._update_labels(0)
        self.message = await self.ctx.reply(**kwargs, view=self)  # type: ignore

    @discord.ui.button(label='≪', style=discord.ButtonStyle.grey)
    async def go_to_first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """go to the first page"""
        await self.show_page(interaction, 0)

    @discord.ui.button(label='Back', style=discord.ButtonStyle.grey)
    async def go_to_previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """go to the previous page"""
        await self.show_checked_page(interaction, self.current_page - 1)

    @discord.ui.button(label='Current', style=discord.ButtonStyle.grey, disabled=True)
    async def go_to_current_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label='Next', style=discord.ButtonStyle.grey)
    async def go_to_next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """go to the next page"""
        await self.show_checked_page(interaction, self.current_page + 1)

    @discord.ui.button(label='≫', style=discord.ButtonStyle.grey)
    async def go_to_last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """go to the last page"""
        # The call here is safe because it's guarded by skip_if
        await self.show_page(interaction, self.source.get_max_pages() - 1)

    @discord.ui.button(label='Quit', style=discord.ButtonStyle.red, row=1)
    async def stop_pages(self, interaction: discord.Interaction, button: discord.ui.Button):
        """stops the pagination session."""
        await interaction.response.defer()
        if self.message:
            await self.message.delete()
        self.stop()


"""
The following definitions are custom made for the specific use case.
"""

class PluginListPaginator(ListPageSource):
    def __init__(self, data: List[Plugin]):
        super().__init__(data, per_page=12)
        self.embed = PidroidEmbed(title=f'{len(data)} plugins have been found matching your query')

    async def format_page(self, menu: PidroidPages, plugins: List[Plugin]):
        self.embed.clear_fields()
        for plugin in plugins:
            self.embed.add_field(
                name=f"#{plugin.id}",
                value=plugin.clean_title,
                inline=True
            )
        return self.embed


class CasePaginator(ListPageSource):
    def __init__(
        self,
        paginator_title: str,
        cases: List[Case],
        *,
        per_page: int = 8,
        compact: bool = False,
        include_original_user_name: bool = False
    ):
        super().__init__(cases, per_page=per_page)
        self.embed = PidroidEmbed(title=paginator_title)
        self.__compact = compact
        self.__include_original_user_name = include_original_user_name

    def _get_field_name(self, case: Case) -> str:
        """"Returns the embed field name for the specified case."""
        if self.__compact:
            return f"#{case.case_id} issued by {case.moderator_name}"
        return f"Case #{case.case_id}: {case.type.value}"

    def _get_field_value(self, case: Case) -> str:
        """"Returns the embed field value for the specified case."""
        if self.__compact:
            if self.__include_original_user_name:
                return f"\"{case.clean_reason}\" issued to {case.user_name} ({case.user_id}) on {format_dt(case.date_issued)}"
            return f"\"{case.clean_reason}\" issued on {format_dt(case.date_issued)}"
        
        if self.__include_original_user_name:
            return (
                f"**Issued to:** {case.user_name} ({case.user_id})\n"
                f"**Issued by:** {case.moderator_name}\n"
                f"**Issued on:** {format_dt(case.date_issued)}\n"
                f"**Reason:** {case.clean_reason.capitalize()}"
            )
        return (
            f"**Issued by:** {case.moderator_name}\n"
            f"**Issued on:** {format_dt(case.date_issued)}\n"
            f"**Reason:** {case.clean_reason.capitalize()}"
        )

    async def format_page(self, _: PidroidPages, cases: List[Case]) -> discord.Embed:
        self.embed.clear_fields()
        for case in cases:
            self.embed.add_field(
                name=self._get_field_name(case), value=self._get_field_value(case), inline=False
            )

        entry_count = len(self.entries)
        if entry_count == 1:
            self.embed.set_footer(text=f'{entry_count} entry')
        else:
            self.embed.set_footer(text=f'{entry_count:,} entries')
        return self.embed