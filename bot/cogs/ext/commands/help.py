from discord.embeds import Embed
from discord.ext import commands
from discord.ext.commands.core import Command
from discord.ext.commands.context import Context
from math import ceil
from typing import List

from client import Pidroid
from cogs.models.categories import Category, BotCategory, UncategorizedCategory
from cogs.utils.embeds import create_embed, error

COMMANDS_PER_PAGE = 6

def get_full_command_name(command: Command):
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

def get_command_documentation(prefix: str, c: Command) -> tuple:
    command_name = get_full_command_name(c)
    description = 'Not documented.'
    if c.brief is not None:
        usage = '**Usage:** `' + prefix + command_name + '`'
        if c.usage is not None:
            usage += ' `' + c.usage + '`'
        description = c.brief + '\n' + usage

    # Fetch command aliases
    aliases = c.aliases
    if len(aliases) > 0:
        description += '\n'
        description += '**Aliases:** `' + '`, `'.join(aliases) + '`.'
    return command_name, description


class HelpCommand(commands.Cog):
    """This class implements a cog which manages the help command of the bot."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client
        self.prefix = self.client.prefix

    def get_all_category_commands(self, category: Category) -> List[Command]:
        "Returns a filtered list of all commands belonging to the specified category."
        cmd_list = []
        for command in self.client.walk_commands():
            orig_kwargs: dict = command.__original_kwargs__
            command_category = orig_kwargs.get("category", UncategorizedCategory)
            if not isinstance(category, command_category):
                continue
            cmd_list.append(command)
        return cmd_list

    def get_visible_category_commands(self, category: Category) -> List[Command]:
        "Returns a filtered list of all visible commands belonging to the specified category."
        cmd_list = []
        for command in self.client.walk_commands():
            if command.hidden:
                continue
            orig_kwargs: dict = command.__original_kwargs__
            command_category = orig_kwargs.get("category", UncategorizedCategory)
            if not isinstance(category, command_category):
                continue
            cmd_list.append(command)
        return cmd_list

    async def clean_commands(self, commands: list) -> list:
        """Returns a list of cleaned commands.\n
        Cleaned in this case refers to checks whether commands can be ran and their documentation created."""
        cleaned_commands = []
        for c in commands:
            c: Command
            # Ignores hidden commands
            if c.hidden:
                continue

            # Generates command documentation
            command_name, description = get_command_documentation(self.prefix, c)

            cleaned_commands.append({'name': command_name, 'description': description})
        cleaned_commands.sort(key=lambda x: x['name'])
        return cleaned_commands

    def return_category_commands(self, category: Category, page: int) -> Embed:
        """Returns an Embed of category commands."""
        command_list = self.get_visible_category_commands(category)

        available_page_count = ceil(len(command_list) / COMMANDS_PER_PAGE)
        if available_page_count == 0:
            return error('This category contains no commands!')

        if page > available_page_count:
            return error('Cannot find such page!')

        embed = create_embed(
            title=f"{category.title} category command listing",
            description=category.description
        )

        commands_per_page = page * COMMANDS_PER_PAGE
        for command in command_list[commands_per_page - COMMANDS_PER_PAGE:commands_per_page]:
            name, description = get_command_documentation(self.prefix, command)
            embed.add_field(name=name, value=description, inline=False)

        embed.set_footer(text=f'Page {page}/{available_page_count}')
        return embed

    @commands.command(
        brief='Returns help command.',
        usage='[category/command] [page]',
        category=BotCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    async def help(self, ctx: Context, search_string: str = None, page: int = 1):
        async with ctx.typing():
            if page < 1:
                page = 1

            # Would ideally want to cache these
            command_object_list = [c for c in self.client.walk_commands()]
            category_object_list = self.client.command_categories

            command_name_list = [get_full_command_name(c) for c in command_object_list]
            category_name_list = [c.title.lower() for c in category_object_list]

            # List all categories
            if search_string is None:
                embed = create_embed(
                    title=f'{self.client.user.name} command category index',
                    description=f'This is a list of all bot commands and their categories. Use `{self.prefix}help [category/command] [page]` to find out more about them!'
                )
                description = ''
                for category in category_object_list:
                    description += f'• **{category.title}** - {category.description}' + '\n'
                embed.add_field(name='Categories', value=description, inline=False)
                await ctx.reply(embed=embed)
                return

            query = search_string.lower()

            # Plain command
            if query in command_name_list:
                command = command_object_list[command_name_list.index(query)]
                if command.hidden:
                    await ctx.reply(embed=error("I could not find any commands by the specified query!"))
                    return

                embed = create_embed(
                    title=f"{get_full_command_name(command)}",
                    description=command.brief or "Not description."
                )

                embed.add_field(name="Usage", value=get_command_usage(self.prefix, command), inline=False)

                aliases = "None."
                if len(command.aliases) > 0:
                    aliases = ', '.join(command.aliases)
                embed.add_field(name="Aliases", value=aliases)

                perm_str = "???"
                permissions = command.__original_kwargs__.get("permissions", [])
                if len(permissions) > 0:
                    perm_str = ', '.join(permissions)
                embed.add_field(name="Permissions", value=perm_str)

                await ctx.reply(embed=embed)
                return

            # Category commands
            if query in category_name_list:
                await ctx.reply(
                    embed=self.return_category_commands(
                        category_object_list[category_name_list.index(query)],
                        page
                    )
                )
                return

            await ctx.reply(embed=error("I could not find any commands by the specified query!"))


def setup(client: Pidroid) -> None:
    client.add_cog(HelpCommand(client))
