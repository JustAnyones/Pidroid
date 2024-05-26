import base64
import logging
import random

from discord import File
from discord.errors import Forbidden
from discord.ext import commands
from discord.ext.commands import BadArgument, MissingRequiredArgument
from discord.ext.commands.context import Context
from discord.member import Member
from io import BytesIO

from pidroid.client import Pidroid
from pidroid.constants import THEOTOWN_GUILD
from pidroid.models.categories import TheoTownCategory
from pidroid.models.view import PaginatingView
from pidroid.services.error_handler import notify
from pidroid.utils import http, format_version_code
from pidroid.utils.decorators import command_checks
from pidroid.utils.embeds import PidroidEmbed, SuccessEmbed
from pidroid.utils.http import Route
from pidroid.utils.paginators import PluginListPaginator
from pidroid.utils.time import utcnow

logger = logging.getLogger("Pidroid")

SUPPORTED_GALLERY_MODES = ['recent', 'trends', 'rating']

def resolve_gallery_mode(query: str | None) -> str | None:
    if query is None:
        return None
    query = query.lower()
    if query in ["trending", "hot", "trends"]:
        return "trends"
    if query in ["new", "recent", "latest"]:
        return "recent"
    if query in ["rating", "top", "best"]:
        return "rating"
    return None

class TheoTownCommandCog(commands.Cog):
    """This class implements a cog for TheoTown API related commands."""

    def __init__(self, client: Pidroid) -> None:
        super().__init__()
        self.client = client
        self.api = self.client.api

    @commands.command(
        brief="Returns the latest game version of TheoTown for all platforms.",
        category=TheoTownCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.user)
    async def version(self, ctx: Context[Pidroid]):
        async with ctx.typing():
            cache = self.client.version_cache
            embed = PidroidEmbed(title="Most recent versions of TheoTown")
            async with await http.get(self.client, "https://bd.theotown.com/get_version") as response:
                version_data = await response.json()
            for version_name in version_data:
                # Ignore Amazon since it's not updated
                if version_name == 'Amazon':
                    continue

                version = format_version_code(version_data[version_name]['version'])
                url: str | None = None
                if version not in cache or cache[version] is None:
                    logger.info(f'URL for version {version} not found in internal cache, querying the API')

                    res = await self.api.get(Route("/private/game/lookup_version", {"query": version}))

                    if res["success"]:
                        url = res["data"]["url"]
                        logger.info(f'Version URL found, internal cache updated with {url}')

                    cache[version] = url
                url = cache[version]
                value = f'[{version}]({url})'
                if url is None:
                    value = version
                embed.add_field(name=version_name, value=value)
            self.client.version_cache = cache
            embed.set_footer(text='Note: this will also include versions which are not yet available to regular users.')
            await ctx.reply(embed=embed)

    @commands.command(
        brief="Returns TheoTown's online mode statistics.",
        aliases=["multiplayer"],
        category=TheoTownCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    @commands.cooldown(rate=1, per=15, type=commands.BucketType.channel)
    @commands.max_concurrency(number=3, per=commands.BucketType.guild)
    async def online(self, ctx: Context[Pidroid]):
        async with ctx.typing():
            res = await self.api.get(Route("/private/game/get_online_statistics"))

            data = res["data"]
            total_plots = data["plots"]["total"]
            free_plots = data["plots"]["free"]
            region_count = data["region_count"]
            population = data["population"]

            # Build and send the embed
            embed = PidroidEmbed(title='Online mode statistics')
            embed.add_field(name='Active regions', value=f'{region_count:,}')
            embed.add_field(name='Total plots', value=f'{total_plots:,}')
            embed.add_field(name='Free plots', value=f'{free_plots:,}')
            embed.add_field(name='Total population', value=f'{population:,}')
            await ctx.reply(embed=embed)

    @commands.command(
        brief='Returns an image from TheoTown\'s in-game gallery.',
        usage='[recent/trends/rating] [random number]',
        aliases=['screenshot'],
        category=TheoTownCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.user)
    async def gallery(self, ctx: Context[Pidroid], mode: str | None = 'recent', number: int | None = None):
        selected_mode = resolve_gallery_mode(mode)

        if selected_mode not in SUPPORTED_GALLERY_MODES:
            raise BadArgument(
                "Wrong mode specified. Allowed modes are `"
                + "`, `".join(SUPPORTED_GALLERY_MODES)
                + "`."
            )

        if number is None:
            number = random.randint(1, 200) # nosec

        try:
            number = int(number)
        except Exception:
            raise BadArgument("Your specified position is incorrect.")

        if number not in range(1, 201):
            raise BadArgument("Number must be between 1 and 200!")
        
        async with ctx.typing():
            res = await self.client.api.get(Route("/public/game/gallery", {"mode": selected_mode, "limit": number}))
            if not res["success"]:
                raise BadArgument("I was unable to retrieve gallery data.")

            data = res["data"]
            screenshot = data[number - 1]

            embed = PidroidEmbed(title=screenshot['name'])
            embed.set_image(url=screenshot['image'])
            embed.set_footer(text=f'#{screenshot["id"]}')
            await ctx.reply(embed=embed)

    @commands.command(
        name='find-plugin',
        brief='Searches the plugin store for the specified plugin.',
        usage='<query>',
        aliases=['findplugin'],
        examples=[
            ("Find plugins named road", 'find-plugin road'),
            ("Find something more precise", 'find-plugin "Indonesia transport pack"'),
            ("Find plugin using its ID", 'find-plugin #14')
        ],
        category=TheoTownCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    @commands.cooldown(rate=2, per=10, type=commands.BucketType.user)
    async def find_plugin_command(self, ctx: Context[Pidroid], query: str): # noqa
        async with ctx.typing():
            is_id = query.startswith("#")
            pl_id = None
            if is_id:
                try:
                    pl_id = int(query.replace("#", ""))
                except ValueError:
                    raise BadArgument("You specified an invalid plugin ID!")

            if not is_id and len(query) <= 2:
                raise BadArgument("Your query is too short! Please make sure it's at least 3 characters long.")

            if not is_id and len(query) > 30:
                raise BadArgument("Your query is too long, please keep it below 30 characters!")

            async with ctx.channel.typing():
                if is_id:
                    assert pl_id is not None
                    plugin_list = await self.api.fetch_plugin_by_id(pl_id)
                else:
                    plugin_list = await self.api.search_plugins(query)

            plugin_count = len(plugin_list)
            if plugin_count == 0:
                raise BadArgument('No plugin could be found by your query.')

            index = 0
            if plugin_count > 1:
                found = False
                for i, plugin in enumerate(plugin_list):
                    if str(plugin.id) == query.replace("#", ""):
                        index = i
                        found = True
                        break

                if not found:
                    pages = PaginatingView(self.client, ctx, source=PluginListPaginator(query, plugin_list))
                    return await pages.send()

            return await ctx.reply(embed=plugin_list[index].to_embed())

    @find_plugin_command.error
    async def on_find_plugin_command_error(self, ctx: Context[Pidroid], error: Exception):
        if isinstance(error, MissingRequiredArgument):
            if error.param.name == "query":
                return await notify(ctx, "Please specify plugin search query.")
        setattr(error, 'unhandled', True)

    @commands.command(
        name='download-plugin',
        brief='Downloads a plugin by the specified ID.',
        usage='<plugin ID>',
        permissions=["TheoTown developer"],
        aliases=['downloadplugin'],
        category=TheoTownCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @command_checks.is_theotown_developer()
    async def downloadplugin(self, ctx: Context[Pidroid], plugin_id: int):
        async with ctx.typing():
            plugins = await self.api.fetch_plugin_by_id(plugin_id, True)
            if len(plugins) == 0:
                raise BadArgument("I could not find any plugins to download by the specified ID!")

            plugin = plugins[0]
            if plugin.download_url is None:
                raise BadArgument(f"Failure encountered while trying to retrieve the plugin file for '{plugin.clean_title}'!")

            _ = await ctx.author.send(f"Here's a link for '{plugin.clean_title}' plugin: {plugin.download_url}")
            return await ctx.reply(f"The download link for '{plugin.clean_title}' plugin has been sent to you via a DM!")

    @commands.command(
        name='link-account',
        brief='Links a discord user account to a TheoTown account.',
        usage='<member> <forum user ID>',
        category=TheoTownCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @command_checks.is_theotown_developer()
    async def link_account(self, ctx: Context[Pidroid], member: Member, forum_id: int):
        # Check if the discord account is linked to anything
        linked_acc = await self.client.api.fetch_linked_account_by_user_id(member.id)
        if linked_acc:
            raise BadArgument(f"{str(member)} is already linked to a forum account!")

        # Check if the forum account is linked to anything
        linked_acc = await self.client.api.fetch_linked_account_by_forum_id(forum_id)
        if linked_acc:
            raise BadArgument("Specified forum account is already linked to a discord account!")

        account = await self.client.api.fetch_theotown_account_by_id(forum_id)
        if account is None:
            raise BadArgument("Specified game account does not exist!")

        _ = await self.client.api.insert_linked_account(member.id, forum_id)
        return await ctx.send(embed=SuccessEmbed(
            f"Discord account {member.mention} has been linked to [{account.forum_account.name}]({account.forum_account.profile_url}) successfully!"
        ))

    @commands.command(
        name='redeem-wage',
        brief='Redeems moderation wage for the linked TheoTown account.',
        category=TheoTownCategory
    )
    @commands.max_concurrency(number=1, per=commands.BucketType.user)
    @commands.bot_has_permissions(send_messages=True)
    async def redeem_wage(self, ctx: Context[Pidroid]):
        # Find the linked account
        linked_acc = await self.client.api.fetch_linked_account_by_user_id(ctx.author.id)
        if linked_acc is None:
            raise BadArgument("Your discord account is not linked to any TheoTown accounts!")

        # Check if last redeem was not within this month
        last_wage_date = linked_acc.date_wage_last_redeemed
        if last_wage_date is not None and last_wage_date.month == utcnow().month:
            raise BadArgument("You've already redeemed the wage for this month!")
        
        # Obtain TT guild
        try:
            guild = await self.client.fetch_guild(THEOTOWN_GUILD, with_counts=False)
        except Forbidden:
            raise BadArgument("Pidroid cannot find the TheoTown server, I cannot determine your wage!")

        # Obtain the member
        member = await self.client.get_or_fetch_member(guild, ctx.author.id)
        if member is None:
            raise BadArgument("You are not a member of the TheoTown server, I cannot determine your wage!")

        # Determine reward by role ID
        roles = [r.id for r in member.roles if r.id in [
            410512375083565066, 368799288127520769, 381899421992091669,
            710914534394560544, 365482773206532096
        ]]

        if len(roles) == 0:
            raise BadArgument("You are not eligible for a wage!")

        # Actual transaction
        res = await self.client.api.get(Route(
            "/private/game/redeem_wage",
            {"forum_id": linked_acc.forum_id, "role_id": roles[-1]}
        ))
        if res["success"]:
            data = res["data"]
            await self.client.api.update_linked_account_by_user_id(member.id, utcnow(), linked_acc.roles)
            return await ctx.reply(f'{data["diamonds_paid"]:,} diamonds have been redeemed to the {data["user"]["name"]} account!')
        raise BadArgument(res["details"])

    @commands.command(
        name='encrypt-plugin',
        brief='Encrypts the provided zip to a .plugin file.',
        category=TheoTownCategory
    )
    @commands.max_concurrency(number=1, per=commands.BucketType.user)
    @commands.bot_has_permissions(send_messages=True)
    async def encrypt_plugin_command(self, ctx: Context[Pidroid]):

        if not ctx.message.attachments:
            raise BadArgument("Please provide the plugin zip file as an attachment.")
        
        attachment = ctx.message.attachments[0]
        if attachment.size > 25*1000*1000:
            raise BadArgument("Your plugin file size must be at most 25 MiB")

        async with ctx.typing():
            payload = {
                "file": await attachment.read(),
                "enforce_manifest": "true"
            }

            parts = attachment.filename.split(".")
            if len(parts) == 1:
                filename = parts[0] + ".plugin"
            else:
                filename = '.'.join(parts[:-1]) + ".plugin"

            async with await http.post(
                self.client,
                url="https://api.svetikas.lt/v1/theotown/encrypt",
                data=payload
            ) as r:
                data = await r.json()

            if data["success"]:
                decoded = base64.b64decode(data["data"])
                io = BytesIO(decoded)
                await ctx.reply(f'Your encrypted plugin file', file=File(io, filename))
                return io.close()
        raise BadArgument(data["details"])

async def setup(client: Pidroid) -> None:
    await client.add_cog(TheoTownCommandCog(client))
