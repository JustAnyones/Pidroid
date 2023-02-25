from discord.embeds import Embed
from discord.ext import commands # type: ignore
from discord.ext.commands.core import Command # type: ignore
from discord.ext.commands.context import Context
from discord.ext.commands.errors import BadArgument
from typing import List, Optional, Tuple

from pidroid.client import Pidroid
from pidroid.cogs.models.categories import Category, BotCategory, UncategorizedCategory
from pidroid.cogs.utils.embeds import PidroidEmbed, ErrorEmbed
from pidroid.cogs.utils.paginators import ListPageSource, PidroidPages


class HelpCommandPaginator(ListPageSource):
    def __init__(self, embed: Embed, prefix: str, data: List[Command]):
        super().__init__(data, per_page=6)
        self.prefix = prefix
        self.embed = embed

    async def format_page(self, menu: PidroidPages, commands: List[Command]):
        self.embed.clear_fields()
        for command in commands:
            name, description = get_command_documentation(self.prefix, command)
            self.embed.add_field(name=name, value=description, inline=False)
        return self.embed

def get_full_command_name(command: Command) -> str:
    """Returns full command name including any command groups."""
    name = ''
    if len(command.parents) > 0:
        for parent in reversed(command.parents):
            name += f'{parent.name} '
    return name + command.name

def get_command_usage(prefix: str, command: Command) -> str:
    usage = '`' + prefix + get_full_command_name(command) + '`'
    if command.usage is not None:
        usage += ' `' + command.usage + '`'
    return usage

def get_command_documentation(prefix: str, c: Command) -> Tuple[str, str]:
    usage = c.usage or ""
    name = prefix + get_full_command_name(c) + " " + usage
    value = c.brief or 'Not documented.'

    # Fetch command aliases
    aliases = c.aliases
    if len(aliases) > 0:
        value += '\n'
        value += '**Aliases:** `' + '`, `'.join(aliases) + '`.'
    return name, value


class HelpCommand(commands.Cog): # type: ignore
    """This class implements a cog which manages the help command of the bot."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client

    def get_visible_category_commands(self, category: Category) -> List[Command]:
        "Returns a filtered list of all visible commands belonging to the specified category."
        cmd_list = []
        for command in self.client.walk_commands():
            if command.hidden:
                continue

            if get_full_command_name(command).startswith("jishaku"):
                continue

            orig_kwargs: dict = command.__original_kwargs__
            command_category = orig_kwargs.get("category", UncategorizedCategory)
            if not isinstance(category, command_category):
                continue
            cmd_list.append(command)
        return cmd_list

    @commands.command( # type: ignore
        brief='Returns help command.',
        usage='[category/command]',
        category=BotCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def help(self, ctx: Context, *, search_string: Optional[str] = None):
        assert self.client.user is not None

        prefixes = await self.client.get_prefixes(ctx.message)
        prefix = prefixes[0]
        # Would ideally want to cache these
        command_object_list = [c for c in self.client.walk_commands()]
        category_object_list = self.client.command_categories

        command_name_list = [get_full_command_name(c) for c in command_object_list]
        category_name_list = [c.title.lower() for c in category_object_list]

        # List all categories
        if search_string is None:
            embed = PidroidEmbed(
                title=f'{self.client.user.name} command category index',
                description=f'This is a list of all bot commands and their categories. Use `{prefix}help [category/command]` to find out more about them!\n\n**Select a category:**'
            )
            for category in category_object_list:
                embed.add_field(name=f"**{category.emote} {category.title}**", value=category.description, inline=False)
            return await ctx.reply(embed=embed)

        query = search_string.lower()

        # Plain command
        if query in command_name_list:
            command: Command = command_object_list[command_name_list.index(query)]
            if command.hidden:
                raise BadArgument("I could not find any commands by the specified query!")

            embed = PidroidEmbed(
                title=f"{get_full_command_name(command)}",
                description=command.brief or "No description."
            )

            embed.add_field(name="Usage", value=get_command_usage(prefix, command), inline=False)

            if len(command.aliases) > 0:
                embed.add_field(name="Aliases", value=', '.join(command.aliases))

            permissions = command.__original_kwargs__.get("permissions", [])
            if len(permissions) > 0:
                embed.add_field(name="Permissions", value=', '.join(permissions))

            return await ctx.reply(embed=embed)

        # Category commands
        if query in category_name_list:
            category = category_object_list[category_name_list.index(query)]
            embed = PidroidEmbed(
                title=f"{category.title} category command listing",
                description=category.description
            )

            pages = PidroidPages(
                source=HelpCommandPaginator(embed, prefix, self.get_visible_category_commands(category)),
                ctx=ctx
            )
            return await pages.start()

        await ctx.reply(embed=ErrorEmbed("I could not find any commands by the specified query!"))


async def setup(client: Pidroid) -> None:
    await client.add_cog(HelpCommand(client))
