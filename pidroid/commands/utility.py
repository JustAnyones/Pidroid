import datetime
import re

from discord.ext import commands
from discord.ext.commands import BadArgument, Context
from discord.utils import format_dt
from typing import Any, override
from urllib.parse import quote_plus as urlencode

from pidroid.client import Pidroid
from pidroid.models.categories import UtilityCategory
from pidroid.models.view import PaginatingView
from pidroid.utils import http, truncate_string
from pidroid.utils.aliases import MessageableGuildChannelTuple
from pidroid.utils.converters import Duration
from pidroid.utils.db.reminder import Reminder
from pidroid.utils.embeds import PidroidEmbed
from pidroid.utils.paginators import ListPageSource
from pidroid.utils.time import datetime_to_duration

MARKDOWN_URL_PATTERN = re.compile(r'\[(.*?)\]')

def term_to_url(match: re.Match[str]) -> str:
    """Replaces match with a markdown hyperlink."""
    item = match.group(1)
    return f'[{item}](https://www.urbandictionary.com/define.php?term={urlencode(item)})'

def parse_urban_text(string: str) -> str:
    """Returns string with URL markdown for Urban Dictionary."""
    text = re.sub(MARKDOWN_URL_PATTERN, term_to_url, string)
    return truncate_string(text, 1000)


class ReminderPaginator(ListPageSource):
    def __init__(self, title: str, data: list[Reminder], extended: bool = False):
        super().__init__(data, per_page=12)
        self.extended = extended
        self.embed = PidroidEmbed(title=title).set_footer(text=f"{len(data)} reminder(s)")

    @override
    async def format_page(self, menu: PaginatingView, page: list[Reminder]):
        offset = menu.current_page * self.per_page + 1
        values = ""
        trunc_len = 22 if self.extended else 10
        for i, reminder in enumerate(page):
            values += f"{i + offset}. \"{truncate_string(reminder.content, trunc_len)}\" to be reminded {format_dt(reminder.date_remind, 'R')} in {reminder.message_url}\n"
        self.embed.description = values.strip()
        return self.embed

class UtilityCommandCog(commands.Cog):
    """This class implements a cog for various utility commands."""

    def __init__(self, client: Pidroid) -> None:
        super().__init__()
        self.client = client

    @commands.command(
        brief="Looks up the specified term on urban dictionary.",
        usage="<term>",
        permissions=["Bot owner"],
        aliases=["ud"],
        category=UtilityCategory
    )
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def urban(self, ctx: Context[Pidroid], *, query: str):
        async with ctx.typing():
            url = "https://api.urbandictionary.com/v0/define?term=" + urlencode(query)
            async with await http.get(self.client, url) as response:
                data: dict[str, list[Any]] = await response.json()
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
                _ = embed.add_field(name='Example', value=example, inline=False)
            _ = embed.add_field(name='Rating', value=f"{definition['thumbs_up']:,} 👍 | {definition['thumbs_down']:,} 👎", inline=False)
            _ = embed.set_footer(text=f"Written on {definition['written_on']} by {definition['author']}")
            return await ctx.reply(embed=embed)

    @commands.hybrid_command(
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
    async def remind_me_command(self, ctx: Context[Pidroid], date: Duration, *, content: str):
        assert isinstance(date, datetime.datetime)

        if datetime_to_duration(date) <= 290: # tolerance
            raise BadArgument("Duration should be at least 5 minutes")
        
        if datetime_to_duration(date) >= 60*60*24*365*10:
            raise BadArgument("Your reminder cannot be set to be reminded more than 10 years from now.")

        if len(content) > 1024:
            raise BadArgument("Please keep the reminder content at most 1024 characters")

        channel_id = None
        if isinstance(ctx.channel, MessageableGuildChannelTuple):
            channel_id = ctx.channel.id

        _ = await self.client.api.insert_reminder(
            user_id=ctx.author.id,
            channel_id=channel_id,
            message_id=ctx.message.id,
            message_url=ctx.message.jump_url,
            content=content,
            date_remind=date
        )

        return await ctx.reply(f"Alright, you will be reminded {format_dt(date, 'R')}")

    @commands.hybrid_group(
        name='reminders',
        brief='List all reminders that you have created and are currently active.',
        category=UtilityCategory,
        invoke_without_command=True,
        fallback='short'
    )
    @commands.bot_has_permissions(send_messages=True)
    async def reminders_command(self, ctx: Context[Pidroid]):
        if ctx.invoked_subcommand is None:
            reminders = await self.client.api.fetch_reminders(user_id=ctx.author.id)
            if not reminders:
                raise BadArgument("You have no active reminders")

            view = PaginatingView(
                self.client, ctx,
                source=ReminderPaginator(f"Active reminders for {ctx.author}", reminders)
            )
            await view.send()

    @reminders_command.command(
        name='extended',
        brief='List an extended list of all reminders that you have created and are currently active.',
        category=UtilityCategory,
    )
    @commands.bot_has_permissions(send_messages=True)
    async def reminders_extended_command(self, ctx: Context[Pidroid]):
        reminders = await self.client.api.fetch_reminders(user_id=ctx.author.id)
        if not reminders:
            raise BadArgument("You have no active reminders")

        view = PaginatingView(
            self.client, ctx,
            source=ReminderPaginator(f"Active reminders for {ctx.author}", reminders, True)
        )
        await view.send()

    @commands.hybrid_command(
        name="remove-reminder",
        brief="Remove the specified reminder.",
        usage="<reminder number>",
        category=UtilityCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    async def remove_reminder_command(self, ctx: Context[Pidroid], reminder_no: int):
        reminders = await self.client.api.fetch_reminders(user_id=ctx.author.id)
        if not reminders:
            raise BadArgument("You have no active reminders")
        
        if reminder_no <= 0 or reminder_no > len(reminders):
            raise BadArgument("Invalid reminder number")
        
        to_remove = reminders[reminder_no - 1]

        await self.client.api.delete_reminder(row=to_remove.id)
        return await ctx.reply("Reminder removed successfully")

async def setup(client: Pidroid) -> None:
    await client.add_cog(UtilityCommandCog(client))
