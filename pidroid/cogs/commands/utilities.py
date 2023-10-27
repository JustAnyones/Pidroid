import datetime
import re

from aiohttp.client_exceptions import ContentTypeError
from discord.ext import commands
from discord.ext.commands import BadArgument, Context
from discord.utils import format_dt
from urllib.parse import quote_plus as urlencode

from pidroid.client import Pidroid
from pidroid.models.categories import UtilityCategory
from pidroid.utils import http, truncate_string
from pidroid.utils.aliases import MessageableGuildChannelTuple
from pidroid.utils.converters import Duration
from pidroid.utils.embeds import PidroidEmbed
from pidroid.utils.time import datetime_to_duration, timestamp_to_date

MARKDOWN_URL_PATTERN = re.compile(r'\[(.*?)\]')

CORONA_API_URL = 'https://disease.sh/v3/covid-19'

def term_to_url(match) -> str:
    """Replaces match with a markdown hyperlink."""
    item = match.group(1)
    return f'[{item}](https://www.urbandictionary.com/define.php?term={urlencode(item)})'

def parse_urban_text(string: str) -> str:
    """Returns string with URL markdown for Urban Dictionary."""
    text = re.sub(MARKDOWN_URL_PATTERN, term_to_url, string)
    return truncate_string(text, 1000)

def get_corona_endpoint(location: str) -> str:
    """Returns correct API endpoint based on location."""
    if location in ["global", "world"]:
        return f'{CORONA_API_URL}/all'
    if location in ["europe", "asia", "africa", "south america", "north america", "oceania"]:
        if location == "oceania":
            return f'{CORONA_API_URL}/continents/Australia%2FOceania'
        return f'{CORONA_API_URL}/continents/{location}'
    return f'{CORONA_API_URL}/countries/{location}'


class UtilityCommands(commands.Cog): # type: ignore
    """This class implements a cog for various utility commands."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client

    @commands.command( # type: ignore
        brief="Looks up the specified term on urban dictionary.",
        usage="<term>",
        permissions=["Bot owner"],
        aliases=["ud"],
        category=UtilityCategory
    )
    @commands.is_owner() # type: ignore
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def urban(self, ctx: Context, *, query: str):
        async with ctx.typing():
            url = "https://api.urbandictionary.com/v0/define?term=" + urlencode(query)
            async with await http.get(self.client, url) as response:
                data = await response.json()
            definitions = data['list']

            # Checks if definition exists
            if not definitions:
                raise BadArgument("I couldn't find any definitions for the specified term!")

            definition = definitions[0]

            # Convert [some words xd] -> [some words xd](https://www.urbandictionary.com/define.php?term=some+words+xd)
            describe = parse_urban_text(definition['definition'])
            example = parse_urban_text(definition['example'])
            embed = PidroidEmbed(title=definition['word'], description=describe, url=definition['permalink'])
            if example:
                embed.add_field(name='Example', value=example, inline=False)
            embed.add_field(name='Rating', value=f"{definition['thumbs_up']:,} 👍 | {definition['thumbs_down']:,} 👎", inline=False)
            embed.set_footer(text=f"Written on {definition['written_on']} by {definition['author']}")
            await ctx.reply(embed=embed)

    @commands.command( # type: ignore
        brief="Displays the coronavirus statistics for the specified place.",
        usage="[country/continent/global]",
        aliases=['corona', 'covid-19', 'covid'],
        category=UtilityCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def coronavirus(self, ctx: Context, *, location: str = "global"):
        async with ctx.typing():
            url = get_corona_endpoint(location.lower())
            try:
                async with await http.get(self.client, url) as response:
                    data = await response.json()
            except ContentTypeError:
                raise BadArgument(f'{CORONA_API_URL} returned corrupted data, please try again later')

            total_vaccinations = None

            try:
                death_count = data["deaths"]
                recovery_count = data["recovered"]
                confirmed_cases = data["cases"]
                active_cases = data["active"]
                total_population = data["population"]
                total_test_count = data['tests']
                cases_per_million = data['casesPerOneMillion']

                last_updated = timestamp_to_date(data['updated'] / 1000, 'hybrid')

                if "country" in data:
                    title = "Covid-19 pandemic stats for " + data["country"]
                    # Attempt to retrieve vaccine data if available
                    try:
                        async with await http.get(self.client, f"{CORONA_API_URL}/vaccine/coverage/countries/{location}?lastdays=1&fullData=true") as r:
                            vaccine_data = await r.json()
                    except ContentTypeError:
                        raise BadArgument(f'{CORONA_API_URL} returned corrupted data, please try again later')
                    if 'timeline' in vaccine_data:
                        total_vaccinations = vaccine_data['timeline'][0]['total']

                elif "continent" in data:
                    title = "Covid-19 pandemic stats for " + data["continent"]

                else:
                    title = "Global Covid-19 pandemic statistics"

                death_proc = round((death_count * 100) / confirmed_cases, 1)
                recov_proc = round((recovery_count * 100) / confirmed_cases, 1)

                embed = PidroidEmbed(title=title)
                embed.add_field(name='Confirmed', value=f'{confirmed_cases:,}', inline=True)
                if recovery_count == 0:
                    embed.add_field(name='Active cases', value='No accurate data available', inline=True)
                    embed.add_field(name='Recovered', value='No data available', inline=True)
                else:
                    embed.add_field(name='Active cases', value=f'{active_cases:,}', inline=True)
                    embed.add_field(name='Recovered', value=f'{recovery_count:,} ({recov_proc}%)', inline=True)
                embed.add_field(name='Fatalities', value=f'{death_count:,} ({death_proc}%)', inline=True)
                embed.add_field(name='Population', value=f'{total_population:,}', inline=True)
                embed.add_field(name='Cases per million', value=f'{cases_per_million:,}', inline=True)
                embed.add_field(name='Total tests', value=f'{total_test_count:,}', inline=True)
                if total_vaccinations is not None:
                    embed.add_field(name='Vaccines administered', value=f'{total_vaccinations:,}')
                if "country" in data:
                    embed.set_thumbnail(url=data["countryInfo"]["flag"])
                embed.set_footer(text=f'Data last updated at {last_updated}')
                await ctx.reply(embed=embed)

            except KeyError:
                raise BadArgument(data['message'])

    @commands.hybrid_command( # type: ignore
        name="remind-me",
        brief="Create a reminder that Pidroid will send you in the specified amount of time.",
        usage="<duration> <content>",
        examples=[
            ("Send reminder 10 hours from now", 'remind-me "10h" feed the fish'),
            ("Send reminder 10 days and 12 hours from now", 'remind-me "10d 12h" update pidroid'),
        ],
        category=UtilityCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    async def remind_me_command(self, ctx: Context, date: Duration, *, content: str):
        assert isinstance(date, datetime.datetime)

        if datetime_to_duration(date) <= 290: # tolerance
            raise BadArgument("Duration should be at least 5 minutes")
        
        if datetime_to_duration(date) >= 60*60*24*365*10:
            raise BadArgument("Your reminder cannot be set as far into the future as 10 years from now.")

        if len(content) > 1024:
            raise BadArgument("Please keep the reminder content at most 1024 characters")

        channel_id = None
        if isinstance(ctx.channel, MessageableGuildChannelTuple):
            channel_id = ctx.channel.id

        await self.client.api.insert_reminder(
            user_id=ctx.author.id,
            channel_id=channel_id,
            message_id=ctx.message.id,
            message_url=ctx.message.jump_url,
            content=content,
            date_remind=date
        )

        await ctx.reply(f"Alright, you will be reminded {format_dt(date, 'R')}")

async def setup(client: Pidroid) -> None:
    await client.add_cog(UtilityCommands(client))
