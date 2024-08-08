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
from __future__ import annotations

import discord

from discord.utils import format_dt
from typing import TYPE_CHECKING, override

from pidroid.models.plugins import Plugin
from pidroid.models.punishments import Case
from pidroid.utils.embeds import PidroidEmbed

if TYPE_CHECKING:
    from pidroid.models.view import PaginatingView

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

    def get_max_pages(self) -> int:
        """An optional abstract method that retrieves the maximum number of pages
        this page source has. Useful for UX purposes.

        Returns
        --------
        :class:`int`
            The maximum number of pages required to properly
            paginate the elements, if given.
        """
        raise NotImplementedError

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

    async def format_page(self, menu, page) -> discord.Embed:
        """|maybecoro|

        An abstract method to format the page.

        This method must return one of the following types.

        If this method returns a :class:`discord.Embed` then it is interpreted
        as returning the ``embed`` keyword argument in :meth:`discord.Message.edit`
        and :meth:`discord.abc.Messageable.send`.

        Parameters
        ------------
        menu: :class:`Menu`
            The menu that wants to format this page.
        page: Any
            The page returned by :meth:`PageSource.get_page`.

        Returns
        ---------
        :class:`discord.Embed`
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

    @override
    def is_paginating(self):
        """:class:`bool`: Whether pagination is required."""
        return len(self.entries) > self.per_page

    @override
    def get_max_pages(self):
        """:class:`int`: The maximum number of pages required to paginate this sequence."""
        return self._max_pages

    @override
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

"""
The following definitions are custom made for the specific use case.
"""

class PluginListPaginator(ListPageSource):
    def __init__(self, original_query: str, data: list[Plugin]):
        super().__init__(data, per_page=12)
        self.embed = (
            PidroidEmbed(title=f'{len(data)} plugins have been found matching your query')
            .set_footer(text=f"Queried: {original_query} | You can use Pfind-plugin id <id> to find out more")
        )

    @override
    async def format_page(self, menu: PaginatingView, page: list[Plugin]):
        _ = self.embed.clear_fields()
        for plugin in page:
            _ = self.embed.add_field(
                name=f"#{plugin.id}",
                value=plugin.clean_title,
                inline=True
            )
        return self.embed


class CasePaginator(ListPageSource):
    def __init__(
        self,
        paginator_title: str,
        cases: list[Case],
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
        
        if case.has_expired:
            expires = "Expired."
        else:
            expires = "Never" if case.date_expires is None else format_dt(case.date_expires)
        
        if self.__include_original_user_name:
            return (
                f"**Issued to:** {case.user_name} ({case.user_id})\n"
                f"**Issued by:** {case.moderator_name}\n"
                f"**Issued on:** {format_dt(case.date_issued)}\n"
                f"**Expires on:** {expires}\n"
                f"**Reason:** {case.clean_reason.capitalize()}"
            )
        return (
            f"**Issued by:** {case.moderator_name}\n"
            f"**Issued on:** {format_dt(case.date_issued)}\n"
            f"**Expires on:** {expires}\n"
            f"**Reason:** {case.clean_reason.capitalize()}"
        )

    @override
    async def format_page(self, menu: PaginatingView, page: list[Case]) -> discord.Embed:
        _ = self.embed.clear_fields()
        for case in page:
            _ = self.embed.add_field(
                name=self._get_field_name(case), value=self._get_field_value(case), inline=False
            )

        entry_count = len(self.entries)
        if entry_count == 1:
            return self.embed.set_footer(text=f'{entry_count} entry')
        return self.embed.set_footer(text=f'{entry_count:,} entries')
