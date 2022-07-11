import re

from discord.ext import commands
from discord.ext.commands import MissingRequiredArgument # type: ignore
from discord.ext.commands.context import Context # type: ignore
from discord.utils import format_dt
from types import SimpleNamespace

from client import Pidroid
from constants import THEOTOWN_FORUM_URL
from cogs.models.categories import TheoTownCategory
from cogs.utils.decorators import command_checks
from cogs.utils.embeds import PidroidEmbed, ErrorEmbed
from cogs.utils.http import Route
from cogs.utils.time import timestamp_to_datetime

class ForumCommands(commands.Cog): # type: ignore
    """This class implements a cog which contains commands for communication via TheoTown forums."""

    def __init__(self, client: Pidroid):
        self.client = client

    @commands.command( # type: ignore
        name='forum-user',
        brief='Returns forum account information for the specified user.',
        usage='<forum username/ID>',
        aliases=['forum-ui'],
        category=TheoTownCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def forum_user(self, ctx: Context, *, username: str):
        async with ctx.typing():
            res = await self.client.api.get(Route(
                "/private/forum/deprecated",
                {"type": "find", "user": username}
            ))
            if res["success"]:
                data = res["data"]
                data = data[0]
                registered = format_dt(timestamp_to_datetime(int(data["user_regdate"])))
                last_online_time = int(data["user_lastvisit"])
                if last_online_time > 0:
                    last_online = format_dt(timestamp_to_datetime(last_online_time))
                else:
                    last_online = 'Never'
                username = data["username"]
                user_id = data["user_id"]
                user_group: str = data["group_name"]
                if user_group.isupper():
                    user_group = user_group.replace("_", " ").capitalize()
                avatar = f'{THEOTOWN_FORUM_URL}/download/file.php?avatar={data["user_avatar"]}'
                embed = PidroidEmbed(title=f'{username}\'s information')
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
                return await ctx.reply(embed=embed)

            await ctx.reply(embed=ErrorEmbed(res["details"]))

    @commands.command( # type: ignore
        name='forum-gift',
        brief='Gifts specified items to the specified user.',
        usage='<diamonds/region coins> <amount> <forum username/ID>',
        permissions=["TheoTown developer"],
        category=TheoTownCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
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
                await ctx.reply(embed=ErrorEmbed("Invalid gift type specified!"))
                return

            # Get regex'ed string position in a string as tuple (start, finish)
            pos = gift_type.regs[0]

            # Convert remaining arguments into list
            parsed_args = command_args[pos[1]:].strip().split()

            # Raise errors for missing arguments
            if len(parsed_args) == 0:
                raise MissingRequiredArgument(SimpleNamespace(name='amount'))
            if len(parsed_args) == 1:
                raise MissingRequiredArgument(SimpleNamespace(name='user'))

            # Parse the arguments for API
            item = command_args[pos[0]:pos[1]].lower()
            amount = parsed_args[0]
            try:
                amount = int(amount) # type: ignore
            except ValueError:
                return await ctx.reply(embed=ErrorEmbed(f"{amount} is not a valid amount!"))

            assert isinstance(amount, int)
            amount = abs(amount)
            user = ' '.join(parsed_args[1:])

            encoded_item = item.replace(' ', '')

            # Send the request to API
            res = await self.client.api.get(Route(
                "/private/game/gift",
                {"username": user, encoded_item: amount}
            ))
            if res["success"]:
                data = res["data"]
                return await ctx.reply(f'{amount:,} {item} have been gifted to {data["name"]}!')
            await ctx.reply(embed=ErrorEmbed(res["details"]))

    @commands.command( # type: ignore
        name='forum-pm',
        brief='Send a forum PM to specified user as Pidroid.',
        usage='<target user ID> <subject> <body>',
        hidden=True,
        category=TheoTownCategory
    )
    @commands.bot_has_permissions(send_messages=True, manage_messages=True) # type: ignore
    @command_checks.is_theotown_developer()
    async def forum_pm(self, ctx: Context, target: int, subject: str, *, text: str):
        async with ctx.typing():
            data = await self.client.api.get(Route(
                "/private/forum/deprecated",
                {"type": "pm", "author": 10911, "target": target, "subject": subject, "text": text}
            ))
            await ctx.message.delete(delay=0)
            await ctx.reply(data["details"])

    @commands.command( # type: ignore
        name='forum-authorise',
        brief='Activates specified user\'s forum account.',
        usage='<forum username/ID>',
        aliases=['forum-auth', 'forum-activate'],
        category=TheoTownCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @command_checks.is_theotown_developer()
    async def forum_authorise(self, ctx: Context, *, user: str):
        async with ctx.typing():
            res = await self.client.api.get(Route(
                "/private/forum/deprecated",
                {"type": "authorise", "user": user}
            ))
            await ctx.reply(res["details"])


async def setup(client: Pidroid) -> None:
    await client.add_cog(ForumCommands(client))
