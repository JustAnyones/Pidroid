import os.path
import random

from discord.ext import commands
from discord.embeds import _EmptyEmbed
from discord.ext.commands.context import Context
from discord.message import Message
from typing import List

from client import Pidroid
from cogs.models.categories import TheoTownCategory
from cogs.utils import http
from cogs.utils.decorators import command_checks
from cogs.utils.embeds import create_embed, error
from cogs.utils.http import Route
from cogs.utils.paginators import PluginListPaginator, MenuPages
from cogs.utils.parsers import format_version_code

ALLOWED_GALLERY_QUERIES = ['recent', 'trends', 'rating']

def parse_faq_entries(entry_list: List[str]) -> str:
    """Returns a list of FAQ queries in a readable string format."""
    entries = []
    for entry in entry_list:
        entries.append(entry['question'].lower())
    return '``' + '``, ``'.join(entries) + '``'

class TheoTownCommands(commands.Cog):
    """This class implements a cog for TheoTown API related commands."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client
        self.api = self.client.api

    @commands.command(
        brief="Returns the latest game version of TheoTown for all platforms.",
        category=TheoTownCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.user)
    async def version(self, ctx: Context):
        async with ctx.typing():
            cache = self.client.version_cache
            embed = create_embed(title="Most recent versions of TheoTown")
            async with await http.get(self.client, "https://bd.theotown.com/get_version") as response:
                version_data = await response.json()
            for versionName in version_data:
                # Ignore Amazon since it's not updated
                if versionName == 'Amazon':
                    continue

                version = format_version_code(version_data[versionName]['version'])
                url = None
                if version not in cache or cache[version] is None:
                    print(f'URL for version {version} not found in internal cache, querying the API')

                    data = await self.api.get(Route("/private/lookup_version", {"query": version}))

                    if data["success"]:
                        url = data["url"]
                        print(f'Version URL found, internal cache updated with {url}')

                    cache[version] = url
                url = cache[version]
                value = f'[{version}]({url})'
                if url is None:
                    value = version
                embed.add_field(name=versionName, value=value)
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
    async def online(self, ctx: Context):
        async with ctx.typing():
            data = await self.api.get(Route("/private/get_online_statistics"))

            r_data = data["data"]
            total_plots = r_data["plots"]["total"]
            free_plots = r_data["plots"]["free"]
            region_count = r_data["region_count"]
            population = r_data["population"]

            # Build and send the embed
            embed = create_embed(title='Online mode statistics')
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
    async def gallery(self, ctx: Context, query: str = 'recent', number: int = None):
        async with ctx.typing():
            query = query.lower()

            if query not in ALLOWED_GALLERY_QUERIES:
                await ctx.reply(embed=error(
                    'Wrong query type specified. Allowed types are `' + '`, `'.join(ALLOWED_GALLERY_QUERIES) + '`.'
                ))
                self.gallery.reset_cooldown(ctx)
                return

            if number is None:
                number = random.randint(1, 200)

            try:
                number = int(number)
            except Exception:
                await ctx.reply(embed=error('Your specified position is incorrect.'))
                self.gallery.reset_cooldown(ctx)
                return

            if number not in range(1, 201):
                await ctx.reply(embed=error('Number must be between 1 and 200!'))
                self.gallery.reset_cooldown(ctx)
                return

            async with await http.get(self.client, f"https://bck0.theotown.com/list_screenshots?mode={query}&limit={number}") as response:
                data = await response.json()

            number -= 1
            screenshot = data['content']['screenshots'][number]

            embed = create_embed(title=screenshot['name'])
            embed.set_image(url=f"https://bck0.theotown.com/get_gallery_file?name={screenshot['real_file']}_a")
            embed.set_footer(text=f'#{screenshot["id"]}')
            await ctx.reply(embed=embed)

    @commands.command(
        name='find-plugin',
        brief='Searches plugin store for the specified plugin.',
        usage='<query>',
        aliases=['findplugin'],
        category=TheoTownCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    @commands.cooldown(rate=2, per=10, type=commands.BucketType.user)
    @command_checks.client_is_pidroid()
    async def findplugin(self, ctx: Context, *, query: str = None):
        async with ctx.typing():
            if query is None:
                await ctx.reply(embed=error('I could not find a query to find a plugin.'))
                self.findplugin.reset_cooldown(ctx)
                return

            if len(query) > 30:
                await ctx.reply(embed=error('Your query is too long, please keep it below 30 characters!'))
                self.findplugin.reset_cooldown(ctx)
                return

            async with ctx.channel.typing():
                plugin_list = await self.api.find_plugin(query)

            plugin_count = len(plugin_list)
            if plugin_count == 0:
                await ctx.reply(embed=error('No plugin could be found by your query.'))
                return

            index = 0
            if plugin_count > 1:
                found = False
                for i, plugin in enumerate(plugin_list):
                    if str(plugin.id) == query.replace("#", ""):
                        index = i
                        found = True
                        break

                if not found:
                    pages = MenuPages(source=PluginListPaginator(plugin_list), clear_reactions_after=True, timeout=60.0)
                    await pages.start(ctx)
                    return

            await ctx.reply(embed=plugin_list[index].to_embed())

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
    async def downloadplugin(self, ctx: Context, *, plugin_id: str = None):
        async with ctx.typing():
            if plugin_id is None:
                await ctx.reply(embed=error('I could not find an ID of the plugin to download!'))
                self.downloadplugin.reset_cooldown(ctx)
                return

            plugins = await self.api.find_plugin(plugin_id, show_hidden=True, narrow_search=True)

            if len(plugins) == 0:
                await ctx.reply(embed=error("I could not find any plugins to download by the specified ID!"))
                return

            plugin = plugins[0]
            data = await self.api.get(Route("/private/get_plugin_download", {"id": plugin.id}))

            if data['status'] == "error":
                await ctx.reply(embed=error(f"I am unable to retrieve the download link for '{plugin.clean_title}' plugin!"))
            else:
                await ctx.reply(f"The download link for '{plugin.clean_title}' plugin has been sent to you via a DM!")
                await ctx.author.send(f"Here's a link for '{plugin.clean_title}' plugin: {data['url']}")

    @commands.command(
        brief='Send a feature suggestion to the suggestions channel.',
        usage='<suggestion>',
        category=TheoTownCategory
    )
    @commands.bot_has_permissions(send_messages=True, attach_files=True, add_reactions=True)  # permissions kind of obsolete
    @command_checks.is_bot_commands()
    @command_checks.is_theotown_guild()
    @commands.cooldown(rate=1, per=60 * 5, type=commands.BucketType.user)
    @command_checks.client_is_pidroid()
    async def suggest(self, ctx: Context, *, suggestion: str = None): # noqa C901
        async with ctx.typing():
            if suggestion is None:
                await ctx.reply(embed=error('Your suggestion cannot be empty!'))
                self.suggest.reset_cooldown(ctx)
                return

            if len(suggestion) < 4:
                await ctx.reply(embed=error('Your suggestion is too short!'))
                self.suggest.reset_cooldown(ctx)
                return

            # If suggestion text is above discord embed description limit
            if len(suggestion) > 2048:
                await ctx.reply(embed=error('The suggestion is too long!'))
                self.suggest.reset_cooldown(ctx)
                return

            attachment_url = None
            channel = self.client.get_channel(409800607466258445)
            file = None

            embed = create_embed(description=suggestion)
            embed.set_author(name=ctx.author, icon_url=ctx.author.avatar.url)
            attachments = ctx.message.attachments
            if attachments:

                if len(attachments) > 1:
                    await ctx.reply(embed=error('Only one picture can be submitted for a suggestion!'))
                    self.suggest.reset_cooldown(ctx)
                    return

                attachment = attachments[0]
                if attachment.size >= 7000000:
                    await ctx.reply(embed=error('Your image is too big to be uploaded!'))
                    self.suggest.reset_cooldown(ctx)
                    return

                filename = attachment.filename
                extension = os.path.splitext(filename)[1]
                if extension.lower() not in ['.png', '.jpg', '.jpeg']:
                    await ctx.reply(embed=error('Could not submit a suggestion: unsupported file extension. Only image files are supported!'))
                    self.suggest.reset_cooldown(ctx)
                    return

                file = await attachment.to_file()
                embed.set_image(url=f'attachment://{filename}')

            message: Message = await channel.send(embed=embed, file=file)
            await message.add_reaction(emoji="✅")
            await message.add_reaction(emoji="❌")
            await message.add_reaction(emoji="❗")
            await message.add_reaction(emoji="⛔")
            if not isinstance(message.embeds[0].image.url, _EmptyEmbed):
                attachment_url = message.embeds[0].image.url
            s_id = await self.api.submit_suggestion(ctx.author.id, message.id, suggestion, attachment_url)
            embed.set_footer(text=f'✅ I like this idea; ❌ I hate this idea; ❗ Already possible.\n#{s_id}')
            await message.edit(embed=embed)
            await ctx.reply('Your suggestion has been submitted to <#409800607466258445> channel successfully!')

    @commands.command(
        brief='Returns frequently asked questions and their indexes.',
        usage='<entry>/[list]',
        category=TheoTownCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    async def faq(self, ctx: Context, *, entry: str = 'list'):
        async with ctx.typing():
            if entry == "list":
                entry_list = await self.api.get_faq_entries()
                entries = parse_faq_entries(entry_list)
                embed = create_embed(title="Frequently asked questions list", description=entries + ".")
                await ctx.reply(embed=embed)
                return

            entries = await self.api.get_faq_entry(entry)
            if entry.lower() == 'cum' or entries is None:  # Using FAQ command fuzziness to show cucumber description is not funny
                await ctx.reply(embed=error('I could not find such FAQ entry!'))
                return

            # No clue how to handle that Pidroid and Pidroid DSA are colliding and won't return
            if len(entries) > 1:
                parsed_entries = parse_faq_entries(entries)
                if not entries[0]['question'].lower() == entry.lower():
                    await ctx.reply(f'Multiple entries matching your term have been found: {parsed_entries}.')
                    return
                await ctx.reply(f"Multiple entries matching your term have been found: {parsed_entries}.\nReturning first entry that matched.")

            entry = entries[0]
            embed = create_embed(title=entry['question'], description=entry['answer'])
            embed.set_footer(text=f"#{entry['id']}")
            await ctx.reply(embed=embed)


def setup(client: Pidroid) -> None:
    client.add_cog(TheoTownCommands(client))
