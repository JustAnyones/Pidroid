from __future__ import annotations

import discord
import logging

from discord import Interaction
from discord.embeds import Embed
from discord.ext import commands
from discord.ext.commands import BadArgument, Command, Context
from typing import TYPE_CHECKING, override

from pidroid.client import Pidroid
from pidroid.models.categories import Category, BotCategory, get_command_documentation, get_command_usage, get_full_command_name
from pidroid.models.view import PaginatingView
from pidroid.utils import get_function_decorators
from pidroid.utils.embeds import PidroidEmbed
from pidroid.utils.paginators import ListPageSource
from pidroid.utils.time import HELP_DURATION_FORMATTING

logger = logging.getLogger('Pidroid')

class HelpCommandPaginator(ListPageSource):
    def __init__(self, embed: Embed, data: list[Command]):
        super().__init__(data, per_page=8)
        self.embed = embed

    @override
    async def format_page(self, menu: PaginatingView, page: list[Command]):
        self.embed.clear_fields()
        for command in page:
            name, description = get_command_documentation(command)
            self.embed.add_field(name=name, value=description, inline=False)
        return self.embed

class CategorySelect(discord.ui.Select[PaginatingView]):

    if TYPE_CHECKING:
        view: HelpCategoryView

    def __init__(self, categories: list[Category]) -> None:
        options: list[discord.SelectOption] = []
        for i, category in enumerate(categories):
            options.append(discord.SelectOption(
                label=category.title,
                emoji=category.emote,
                description=category.description,
                value=str(i)
            ))
        super().__init__(placeholder="Select command category", options=options)

    @override
    async def callback(self, interaction: Interaction):
        success = await self.view.change_category(interaction, self.values[0])
        if not success:
            await interaction.response.send_message("You selected a category that does not exist!", ephemeral=True)

class HelpCategoryView(PaginatingView):

    def __init__(self, client: Pidroid, ctx: Context[Pidroid], *, timeout: float = 600):
        super().__init__(client, ctx, timeout=timeout)
        self._prefix = self._ctx.prefix or "P"

        self.__categories: list[Category] = []
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
                f"This is a help page for {self._client.user.name} bot. "
                "You can view a specific command category by selecting it in the dropdown menu below.\n\n"
                f"You can check out any command in more detail by running {self._ctx.prefix}help [command name]."
            )
        )

        # lifted from robo danny by Rapptz and adapted for Pidroid
        _ = self._embed.add_field(
            name="How do I use this bot?",
            value="Reading the bot help signatures are pretty simple.",
            inline=False,
        ).add_field(
            name="<argument>",
            value="This means the command argument is required.",
        ).add_field(
            name="[argument]",
            value="This means the command argument is optional."
        ).add_field(
            name="[A/B]",
            value=(
                "This means that it can be either A or B.\n"
                "Now that you know the basics, it should be noted that...\n"
                "__**You do not type in the brackets!**__"
            ),
            inline=False,
        ).add_field(
            name="Specifying multiple arguments",
            value=(
                "Commands that accept multiple arguments or specific arguments require quotations around the argument.\n"
                'Example: ``Ptag create "My epic tag" Lots of text, blah blah blah``.\n'
                "**Certain commands do not need quotations for the last argument** in the case of "
                "``Ptag create``, ``Psuggest`` purely for convenience sake."
            )
        ).add_field(
            name="Specifying duration",
            value=HELP_DURATION_FORMATTING
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
        self._embed.set_footer(
            text=(
                "You can view a specific command in greater detail using "
                f"{self._ctx.prefix}help [command name]"
            )
        )

        source = HelpCommandPaginator(
            self._embed,
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

class HelpCommandCog(commands.Cog):
    """This class implements a cog which manages the help command of the bot."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client
        self.show_usable = True

    def search_command(self, query: str) -> Command | None:
        """Returns a single command matching the query."""
        lowercase_query = query.lower()
        for command in self.client.walk_commands():
            if (get_full_command_name(command) == lowercase_query
                and not command.hidden):
                return command
        return None

    @commands.hybrid_command(
        name="help",
        brief="Returns the help menu with all the commands that you can use.",
        usage="[command]",
        examples=[
            ("View help page for the help command", 'help help')
        ],
        category=BotCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    async def help_command(
        self,
        ctx: Context[Pidroid],
        *,
        search_string: str | None = None
    ):
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
                description=command.__original_kwargs__.get("info", None) or command.brief or "No description."
            )
            embed.add_field(name="Usage", value=get_command_usage(prefix, command), inline=False)

            # List aliases
            if len(command.aliases) > 0:
                embed.add_field(name="Aliases", value=', '.join(command.aliases), inline=False)

            # Display the requirements to run the command
            requirements = []
            for decorator in get_function_decorators(command.callback):
                print(decorator)
                if decorator.is_a_check():
                    requirements.append("- " + decorator.requirement_text)
            if requirements:
                embed.add_field(name="Run requirements", value='\n'.join(requirements))

            # Display whether the command can be ran
            can_run = False
            try:
                can_run = await command.can_run(ctx)
            except Exception:
                pass
            embed.add_field(name="Can you run it here?", value="Yes" if can_run else "No")

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
    await client.add_cog(HelpCommandCog(client))
