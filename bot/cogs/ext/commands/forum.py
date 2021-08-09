import re

from discord.ext import commands
from discord.ext.commands import MissingRequiredArgument
from discord.ext.commands.context import Context
from discord.utils import format_dt
from types import SimpleNamespace

from client import Pidroid
from constants import THEOTOWN_FORUM_URL
from cogs.models.categories import TheoTownCategory
from cogs.utils.checks import is_number
from cogs.utils.decorators import command_checks
from cogs.utils.embeds import build_embed, error
from cogs.utils.http import Route
from cogs.utils.time import timestamp_to_datetime

class ForumCommands(commands.Cog):
    """This class implements a cog which contains commands for communication via TheoTown forums."""

    def __init__(self, client: Pidroid):
        self.client = client
        self.api = self.client.api

    @commands.command(
        name='forum-user',
        brief='Returns forum account information for the specified user.',
        usage='<forum username/ID>',
        aliases=['forum-ui'],
        category=TheoTownCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    async def forum_user(self, ctx: Context, *, username: str):
        async with ctx.typing():
            data = await self.api.get(Route(
                "/private/forum",
                {"type": "find", "user": username}
            ))
            try:
                data = data[0]
                registered = format_dt(timestamp_to_datetime(int(data["user_regdate"])))
                last_online = int(data["user_lastvisit"])
                if last_online > 0:
                    last_online = format_dt(timestamp_to_datetime(last_online))
                else:
                    last_online = 'Never'
                username = data["username"]
                user_id = data["user_id"]
                user_group: str = data["group_name"]
                if user_group.isupper():
                    user_group = user_group.replace("_", " ").capitalize()
                avatar = f'{THEOTOWN_FORUM_URL}/download/file.php?avatar={data["user_avatar"]}'
                embed = build_embed(title=f'{username}\'s information')
                embed.add_field(name='Username', value=username, inline=True)
                embed.add_field(name='ID', value=f'[{user_id}]({THEOTOWN_FORUM_URL}/memberlist.php?mode=viewprofile&u={user_id})', inline=True)
                embed.add_field(name='Group', value=user_group, inline=True)
                embed.add_field(name='Rank', value=data["rank_title"], inline=True)
                embed.add_field(name='Post count', value=data["user_posts"], inline=True)
                embed.add_field(name='Reaction count', value=data["user_reactions"], inline=True)
                embed.add_field(name='Plugins', value=f'[Forum plugins]({THEOTOWN_FORUM_URL}/search.php?author_id={user_id}&fid%5B%5D=43&sc=1&sr=topics&sk=t&sf=firstpost)\n[Plugin store plugins]({THEOTOWN_FORUM_URL}/plugins/list?mode=user&user_id={user_id})', inline=False)
                embed.add_field(name='Last online', value=last_online, inline=True)
                embed.add_field(name='Registered', value=registered, inline=True)
                embed.set_thumbnail(url=avatar)
                await ctx.reply(embed=embed)
            except (KeyError, IndexError):
                await ctx.reply(embed=error("Cannot find the specified user"))

    @commands.command(
        name='forum-gift',
        brief='Gifts specified items to the specified user.',
        usage='<diamonds/region coins> <amount> <forum username/ID>',
        permissions=["TheoTown developer"],
        category=TheoTownCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @command_checks.is_theotown_developer()
    async def forum_gift(self, ctx: Context, *args):
        async with ctx.typing():
            if len(args) == 0:
                raise MissingRequiredArgument(SimpleNamespace(name='item'))

            # Join arguments into a single string
            command_args = ' '.join(args[0:])

            # Regex to find if valid gift is specified
            gift_type = re.match('(?i)(?:diamonds)|(?:region coins)', command_args)
            if not gift_type:
                await ctx.reply(embed=error("Invalid gift type specified!"))
                return

            # Get regex'ed string position in a string as tuple (start, finish)
            pos = gift_type.regs[0]

            # Convert remaining arguments into list
            args = command_args[pos[1]:].strip().split()

            # Raise errors for missing arguments
            if len(args) == 0:
                raise MissingRequiredArgument(SimpleNamespace(name='amount'))
            if len(args) == 1:
                raise MissingRequiredArgument(SimpleNamespace(name='user'))

            # Parse the arguments for API
            item = command_args[pos[0]:pos[1]].lower()
            amount = args[0]
            if not is_number(amount):
                await ctx.reply(embed=error(f"{amount} is not a valid amount!"))
                return
            amount = abs(int(amount))
            user = ' '.join(args[1:])

            encoded_item = item.replace(' ', '')

            # Send the request to API
            data = await self.api.get(Route(
                "/private/gift",
                {"username": user, encoded_item: amount}
            ))
            try:
                await ctx.reply(
                    f'{amount:,} {item} have been gifted to {data["name"]}!'
                )
            except KeyError:
                await ctx.reply(embed=error(f"An unknown error has occured while trying to gift {item} to {user}!"))

    @commands.command(
        name='forum-pm',
        brief='Send a forum PM to specified user as Pidroid.',
        usage='<target user ID> <subject> <body>',
        hidden=True,
        category=TheoTownCategory
    )
    @commands.bot_has_permissions(send_messages=True, manage_messages=True)
    @command_checks.is_theotown_developer()
    async def forum_pm(self, ctx: Context, target: int, subject: str, *, text: str):
        async with ctx.typing():
            data = await self.api.get(Route(
                "/private/forum",
                {"type": "pm", "author": 10911, "target": target, "subject": subject, "text": text}
            ))
            await ctx.message.delete(delay=0)
            await ctx.reply(data["details"])

    @commands.command(
        name='forum-authorise',
        brief='Activates specified user\'s forum account.',
        usage='<forum username/ID>',
        aliases=['forum-auth', 'forum-activate'],
        category=TheoTownCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @command_checks.is_theotown_developer()
    async def forum_authorise(self, ctx: Context, *, user: str):
        async with ctx.typing():
            data = await self.api.get(Route(
                "/private/forum",
                {"type": "authorise", "user": user}
            ))
            await ctx.reply(data["details"])


def setup(client: Pidroid) -> None:
    client.add_cog(ForumCommands(client))
