import inspect
import re

from discord.ext import commands
from discord.ext.commands import MissingRequiredArgument, BadArgument, Parameter # type: ignore
from discord.ext.commands.context import Context # type: ignore
from discord.utils import format_dt

from pidroid.client import Pidroid
from pidroid.cogs.handlers.error_handler import notify
from pidroid.models.accounts import ForumAccount
from pidroid.models.categories import TheoTownCategory
from pidroid.utils.decorators import command_checks
from pidroid.utils.embeds import PidroidEmbed, ErrorEmbed, SuccessEmbed
from pidroid.utils.http import Route

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
    async def forum_user_command(self, ctx: Context, username: str):
        async with ctx.typing():
            res = await self.client.api.get(Route(
                "/private/forum/find_account",
                {"query": username}
            ))
            if not res["success"]:
                raise BadArgument(res["details"])

            data = res["data"]
            account = ForumAccount(data[0])
            if account.date_latest_login is None:
                last_online = "Never"
            else:
                last_online = format_dt(account.date_latest_login)
            embed = PidroidEmbed(title=f'{account.name}\'s information')
            embed.add_field(name='Username', value=account.name, inline=True)
            embed.add_field(name='ID', value=f'[{account.id}]({account.profile_url})', inline=True)
            embed.add_field(name='Group', value=account.group_name, inline=True)
            embed.add_field(name='Rank', value=account.rank, inline=True)
            embed.add_field(name='Post count', value=account.post_count, inline=True)
            embed.add_field(name='Reaction count', value=account.reaction_count, inline=True)
            embed.add_field(name='Plugins', value=f'[Forum plugins]({account.forum_plugin_url})\n[Plugin store plugins]({account.plugin_store_url})', inline=False)
            embed.add_field(name='Last online', value=last_online, inline=True)
            embed.add_field(name='Registered', value=format_dt(account.date_registered), inline=True)
            embed.set_thumbnail(url=account.avatar_url)
            await ctx.reply(embed=embed)

    @forum_user_command.error
    async def on_forum_user_command_error(self, ctx: Context, error):
        if isinstance(error, MissingRequiredArgument):
            if error.param.name == "username":
                return await notify(ctx, "Please specify the username to view the information for.")
        setattr(error, 'unhandled', True)

    # TODO: refactor arguments
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
                raise MissingRequiredArgument(Parameter("item", inspect.Parameter.POSITIONAL_OR_KEYWORD, None, None))

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
                raise MissingRequiredArgument(Parameter("amount", inspect.Parameter.POSITIONAL_OR_KEYWORD, None, None))
            if len(parsed_args) == 1:
                raise MissingRequiredArgument(Parameter("user", inspect.Parameter.POSITIONAL_OR_KEYWORD, None, None))

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
            raise BadArgument(res["details"])

    @commands.command( # type: ignore
        name='forum-authorise',
        brief='Activates specified user\'s forum account.',
        usage='<forum username/ID>',
        aliases=['forum-auth', 'forum-activate'],
        category=TheoTownCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @command_checks.is_theotown_developer()
    async def forum_authorise_command(self, ctx: Context, user: str):
        async with ctx.typing():
            res = await self.client.api.get(Route(
                "/private/forum/activate_account",
                {"user": user}
            ))
            if res["success"]:
                return await ctx.reply(embed=SuccessEmbed(res['details']))
            raise BadArgument(res["details"])

    @forum_authorise_command.error
    async def on_forum_authorise_command_error(self, ctx: Context, error):
        if isinstance(error, MissingRequiredArgument):
            if error.param.name == "username":
                return await notify(ctx, "Please specify the username of the user you are trying to authorize.")
        setattr(error, 'unhandled', True)

async def setup(client: Pidroid) -> None:
    await client.add_cog(ForumCommands(client))
