import os.path
import random

from contextlib import suppress
from discord.ext import commands
from discord.errors import HTTPException
from discord.ext.commands.context import Context # type: ignore
from discord.message import Message
from typing import Optional

from client import Pidroid
from cogs.models.categories import TheoTownCategory
from cogs.utils import http
from cogs.utils.decorators import command_checks
from cogs.utils.embeds import PidroidEmbed, ErrorEmbed
from cogs.utils.http import Route
from cogs.utils.paginators import PidroidPages, PluginListPaginator
from cogs.utils.parsers import format_version_code

SUPPORTED_GALLERY_MODES = ['recent', 'trends', 'rating']

def handle_wrong_gallery_modes(query: str) -> Optional[str]:
    if query in ["trending", "hot", "trends"]:
        return "trends"
    if query in ["new", "recent", "latest"]:
        return "recent"
    if query in ["rating", "top", "best"]:
        return "rating"
    return None

class TheoTownCommands(commands.Cog): # type: ignore
    """This class implements a cog for TheoTown API related commands."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client
        self.api = self.client.api

    @commands.command( # type: ignore
        brief="Returns the latest game version of TheoTown for all platforms.",
        category=TheoTownCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.user) # type: ignore
    async def version(self, ctx: Context):
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
                url = None
                if version not in cache or cache[version] is None:
                    print(f'URL for version {version} not found in internal cache, querying the API')

                    res = await self.api.get(Route("/private/game/lookup_version", {"query": version}))

                    if res["success"]:
                        url = res["data"]["url"]
                        print(f'Version URL found, internal cache updated with {url}')

                    cache[version] = url
                url = cache[version]
                value = f'[{version}]({url})'
                if url is None:
                    value = version
                embed.add_field(name=version_name, value=value)
            self.client.version_cache = cache
            embed.set_footer(text='Note: this will also include versions which are not yet available to regular users.')
            await ctx.reply(embed=embed)

    @commands.command( # type: ignore
        brief="Returns TheoTown's online mode statistics.",
        aliases=["multiplayer"],
        category=TheoTownCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @commands.guild_only() # type: ignore
    @commands.cooldown(rate=1, per=15, type=commands.BucketType.channel) # type: ignore
    @commands.max_concurrency(number=3, per=commands.BucketType.guild) # type: ignore
    async def online(self, ctx: Context):
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

    @commands.command( # type: ignore
        brief='Returns an image from TheoTown\'s in-game gallery.',
        usage='[recent/trends/rating] [random number]',
        aliases=['screenshot'],
        category=TheoTownCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.user) # type: ignore
    async def gallery(self, ctx: Context, mode: str = 'recent', number: int = None):
        async with ctx.typing():
            selected_mode = handle_wrong_gallery_modes(mode.lower())

            if selected_mode not in SUPPORTED_GALLERY_MODES:
                self.gallery.reset_cooldown(ctx)
                return await ctx.reply(embed=ErrorEmbed(
                    'Wrong mode specified. Allowed modes are `' + '`, `'.join(SUPPORTED_GALLERY_MODES) + '`.'
                ))

            if number is None:
                number = random.randint(1, 200) # nosec

            try:
                number = int(number)
            except Exception:
                self.gallery.reset_cooldown(ctx)
                return await ctx.reply(embed=ErrorEmbed('Your specified position is incorrect.'))

            if number not in range(1, 201):
                self.gallery.reset_cooldown(ctx)
                return await ctx.reply(embed=ErrorEmbed('Number must be between 1 and 200!'))

            res = await self.client.api.get(Route("/public/game/gallery", {"mode": selected_mode, "limit": number}))
            if not res["success"]:
                return await ctx.reply(embed=ErrorEmbed("Unable to retrieve gallery data!"))

            data = res["data"]
            screenshot = data[number - 1]

            embed = PidroidEmbed(title=screenshot['name'])
            embed.set_image(url=screenshot['image'])
            embed.set_footer(text=f'#{screenshot["id"]}')
            await ctx.reply(embed=embed)

    @commands.command( # type: ignore
        name='find-plugin',
        brief='Searches plugin store for the specified plugin.',
        usage='<query>',
        aliases=['findplugin'],
        category=TheoTownCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @commands.guild_only() # type: ignore
    @commands.cooldown(rate=2, per=10, type=commands.BucketType.user) # type: ignore
    async def findplugin(self, ctx: Context, *, query: str = None): # noqa
        async with ctx.typing():
            if query is None:
                await ctx.reply(embed=ErrorEmbed('I could not find a query to find a plugin.'))
                self.findplugin.reset_cooldown(ctx)
                return

            is_id = query.startswith("#")
            if is_id:
                try:
                    pl_id = int(query.replace("#", ""))
                except ValueError:
                    await ctx.reply(embed=ErrorEmbed('You specified an invalid plugin ID!'))
                    self.findplugin.reset_cooldown(ctx)
                    return

            if not is_id and len(query) <= 2:
                await ctx.reply(embed=ErrorEmbed('Your query is too short! Please keep it at least 3 characters long.'))
                self.findplugin.reset_cooldown(ctx)
                return

            if not is_id and len(query) > 30:
                await ctx.reply(embed=ErrorEmbed('Your query is too long, please keep it below 30 characters!'))
                self.findplugin.reset_cooldown(ctx)
                return

            async with ctx.channel.typing():
                if is_id:
                    assert pl_id is not None
                    plugin_list = await self.api.fetch_plugin_by_id(pl_id)
                else:
                    plugin_list = await self.api.search_plugins(query)

            plugin_count = len(plugin_list)
            if plugin_count == 0:
                return await ctx.reply(embed=ErrorEmbed('No plugin could be found by your query.'))

            index = 0
            if plugin_count > 1:
                found = False
                for i, plugin in enumerate(plugin_list):
                    if str(plugin.id) == query.replace("#", ""):
                        index = i
                        found = True
                        break

                if not found:
                    pages = PidroidPages(PluginListPaginator(plugin_list), ctx=ctx)
                    return await pages.start()

            await ctx.reply(embed=plugin_list[index].to_embed())

    @commands.command( # type: ignore
        name='download-plugin',
        brief='Downloads a plugin by the specified ID.',
        usage='<plugin ID>',
        permissions=["TheoTown developer"],
        aliases=['downloadplugin'],
        category=TheoTownCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @command_checks.is_theotown_developer()
    async def downloadplugin(self, ctx: Context, *, plugin_id: str = None):
        async with ctx.typing():
            if plugin_id is None:
                await ctx.reply(embed=ErrorEmbed('I could not find an ID of the plugin to download!'))
                self.downloadplugin.reset_cooldown(ctx)
                return

            plugins = await self.api.fetch_plugin_by_id(plugin_id, True)
            if len(plugins) == 0:
                return await ctx.reply(embed=ErrorEmbed("I could not find any plugins to download by the specified ID!"))

            plugin = plugins[0]
            if plugin.download_url is None:
                return await ctx.reply(embed=ErrorEmbed(
                    f"Failure encountered while trying to retrieve the plugin file for '{plugin.clean_title}'!"
                ))

            await ctx.reply(f"The download link for '{plugin.clean_title}' plugin has been sent to you via a DM!")
            await ctx.author.send(f"Here's a link for '{plugin.clean_title}' plugin: {plugin.download_url}")

    @commands.command( # type: ignore
        brief='Send a feature suggestion to the suggestions channel.',
        usage='<suggestion>',
        category=TheoTownCategory
    )
    @commands.bot_has_permissions(send_messages=True, attach_files=True, add_reactions=True) # type: ignore # permissions kind of obsolete
    @command_checks.is_bot_commands()
    @command_checks.is_theotown_guild()
    @commands.cooldown(rate=1, per=60 * 5, type=commands.BucketType.user) # type: ignore
    @command_checks.client_is_pidroid()
    async def suggest(self, ctx: Context, *, suggestion: str = None): # noqa C901
        async with ctx.typing():
            if suggestion is None:
                await ctx.reply(embed=ErrorEmbed('Your suggestion cannot be empty!'))
                self.suggest.reset_cooldown(ctx)
                return

            if len(suggestion) < 4:
                await ctx.reply(embed=ErrorEmbed('Your suggestion is too short!'))
                self.suggest.reset_cooldown(ctx)
                return

            # If suggestion text is above discord embed description limit
            if len(suggestion) > 2048:
                await ctx.reply(embed=ErrorEmbed('The suggestion is too long!'))
                self.suggest.reset_cooldown(ctx)
                return

            attachment_url = None
            channel = self.client.get_channel(409800607466258445)
            file = None

            embed = PidroidEmbed(description=suggestion)
            embed.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
            attachments = ctx.message.attachments
            if attachments:

                if len(attachments) > 1:
                    await ctx.reply(embed=ErrorEmbed('Only one picture can be submitted for a suggestion!'))
                    self.suggest.reset_cooldown(ctx)
                    return

                attachment = attachments[0]
                if attachment.size >= 7000000:
                    await ctx.reply(embed=ErrorEmbed('Your image is too big to be uploaded!'))
                    self.suggest.reset_cooldown(ctx)
                    return

                filename = attachment.filename
                extension = os.path.splitext(filename)[1]
                if extension.lower() not in ['.png', '.jpg', '.jpeg']:
                    await ctx.reply(embed=ErrorEmbed('Could not submit a suggestion: unsupported file extension. Only image files are supported!'))
                    self.suggest.reset_cooldown(ctx)
                    return

                file = await attachment.to_file()
                embed.set_image(url=f'attachment://{filename}')

            message: Message = await channel.send(embed=embed, file=file)
            await message.add_reaction("✅")
            await message.add_reaction("❌")
            await message.add_reaction("❗")
            await message.add_reaction("⛔")
            if message.embeds[0].image.url is not None:
                attachment_url = message.embeds[0].image.url
            s_id = await self.api.submit_suggestion(ctx.author.id, message.id, suggestion, attachment_url)
            embed.set_footer(text=f'✅ I like this idea; ❌ I hate this idea; ❗ Already possible.\n#{s_id}')
            await message.edit(embed=embed)
            with suppress(HTTPException):
                await ctx.reply('Your suggestion has been submitted to <#409800607466258445> channel successfully!')

async def setup(client: Pidroid) -> None:
    await client.add_cog(TheoTownCommands(client))
