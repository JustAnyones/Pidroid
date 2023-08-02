from __future__ import annotations

import discord
import logging

from discord import Interaction
from discord.embeds import Embed
from discord.ext import commands
from discord.ext.commands import Context # type: ignore
from discord.ext.commands.core import Command # type: ignore
from discord.ext.commands.context import Context
from discord.ext.commands.errors import BadArgument
from typing import TYPE_CHECKING, List, Optional

from pidroid.client import Pidroid
from pidroid.models.categories import Category, BotCategory, get_command_documentation, get_command_usage, get_full_command_name
from pidroid.models.view import PaginatingView
from pidroid.utils.embeds import PidroidEmbed
from pidroid.utils.paginators import ListPageSource

logger = logging.getLogger('Pidroid')

class HelpCommandPaginator(ListPageSource):
    def __init__(self, embed: Embed, prefix: str, data: List[Command]):
        super().__init__(data, per_page=8)
        self.prefix = prefix
        self.embed = embed

    async def format_page(self, _: PaginatingView, commands: List[Command]):
        self.embed.clear_fields()
        for command in commands:
            name, description = get_command_documentation(self.prefix, command)
            self.embed.add_field(name=name, value=description, inline=False)
        return self.embed

class CategorySelect(discord.ui.Select):

    if TYPE_CHECKING:
        view: HelpCategoryView

    def __init__(self, categories: List[Category]) -> None:
        options = []
        for i, category in enumerate(categories):
            options.append(discord.SelectOption(
                label=category.title,
                emoji=category.emote,
                description=category.description,
                value=str(i)
            ))
        super().__init__(placeholder="Select category", options=options)

    async def callback(self, interaction: Interaction):
        success = await self.view.change_category(interaction, self.values[0])
        if not success:
            await interaction.response.send_message("You selected a category that does not exist!", ephemeral=True)

class HelpCategoryView(PaginatingView):

    def __init__(self, client: Pidroid, ctx: Context, *, timeout: float = 600):
        super().__init__(client, ctx, timeout=timeout)
        self._prefix = self._ctx.prefix or "P"

        self.__categories: List[Category] = []
        for category in self._client.command_categories:
            if category.get_visible_commands():
                self.__categories.append(category)
        self._reset_view()

    def _reset_view(self) -> None:
        """Resets the message to initial state."""
        assert self._client.user

        self._embed = PidroidEmbed(
            title=f"{self._client.user.name} command category index",
            description=(
                f"This is a category list of {self._client.user.name}'s commands. "
                "You can view the category by selecting it using the selector provided below.\n\n"
                f"You can check out any command in more detail by running {self._ctx.prefix}help [command name].\n"
                "Commands that accept multiple arguments or specific arguments require quotations around the argument.\n"
                "**Command categories:**"
            )
        )
        for category in self.__categories:
            self._embed.add_field(
                name=f"**{category.emote} {category.title}**",
                value=category.description,
                inline=False
            )

        self.add_item(CategorySelect(self.__categories))
        self.add_item(self.close_button)

    async def change_category(self, interaction: Interaction, category_index: str) -> bool:
        """Changes category to the specified one. Returns boolean denoting whether operation was successful."""    
        try:
            index = int(category_index)
        except ValueError:
            return False
        
        if index >= len(self.__categories):
            return False
    
        category = self.__categories[index]

        self._embed = PidroidEmbed(
            title=f"{category.title} category command listing",
            description=category.description
        )

        source = HelpCommandPaginator(
            self._embed,
            self._prefix,
            category.get_visible_commands()
        )

        # Set the pagination source and initialize it
        self.set_source(source)
        await self.initialize_paginator()

        # Create the buttons
        self.clear_items()
        self.add_item(CategorySelect(self.__categories))
        self.add_pagination_buttons(close_button=False)
        self.add_item(self.close_button)

        # Update the view
        await self._update_view(interaction)
        return True

class HelpCommand(commands.Cog): # type: ignore
    """This class implements a cog which manages the help command of the bot."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client

    def search_command(self, query: str) -> Optional[Command]:
        """Returns a single command matching the query."""
        lowercase_query = query.lower()
        for command in self.client.walk_commands():
            if (get_full_command_name(command) == lowercase_query
                and not command.hidden):
                return command
        return None

    @commands.hybrid_command( # type: ignore
        name="help",
        brief="Returns the help command.",
        usage="[command]",
        examples=[
            ("View help page for the help command", 'help help')
        ],
        category=BotCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def help_command(self, ctx: Context, *, search_string: Optional[str] = None):
        # Browse categories
        if search_string is None:
            view = HelpCategoryView(self.client, ctx)
            return await view.send()
        
        # Search commands
        command = self.search_command(search_string)
        if command:
            prefix = ctx.prefix or "P"
            embed = PidroidEmbed(
                title=f"{get_full_command_name(command)}",
                description=command.brief or "No description."
            )
            embed.add_field(name="Usage", value=get_command_usage(prefix, command), inline=False)

            # List aliases
            if len(command.aliases) > 0:
                embed.add_field(name="Aliases", value=', '.join(command.aliases))

            # List permissions, DEPRECATED
            permissions = command.__original_kwargs__.get("permissions", [])
            if len(permissions) > 0:
                embed.add_field(name="Permissions", value=', '.join(permissions))

            # List custom examples
            examples = command.__original_kwargs__.get("examples", [])
            if examples:

                formatted = ""
                for example in examples:
                    desc, cmd = example
                    formatted += f"- **{desc}**\n``{prefix}{cmd}``\n"

                embed.add_field(name="Examples", value=formatted.strip(), inline=False)

            return await ctx.reply(embed=embed)


        raise BadArgument("I could not find any commands matching your query.")

async def setup(client: Pidroid) -> None:
    await client.add_cog(HelpCommand(client))
