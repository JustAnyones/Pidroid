from __future__ import annotations

import logging

from datetime import timedelta
from discord import (
    app_commands,
    Color,
    File,
    Member,
    Message,
    Object,
    ui
)
from discord.ext import commands
from discord.ext.commands import BadArgument, Context
from typing import Callable

from pidroid.client import Pidroid
from pidroid.models.categories import ModerationCategory
from pidroid.modules.core.ui.view import ReadonlyContainerView
from pidroid.modules.moderation.models.types import Timeout2
from pidroid.utils.aliases import MessageableGuildChannel, MessageableGuildChannelTuple
from pidroid.utils.checks import is_guild_moderator
from pidroid.utils.decorators import command_checks
from pidroid.utils.file import Resource
from pidroid.utils.time import delta_to_datetime

logger = logging.getLogger("pidroid.legacy-moderation")

def is_not_pinned(message: Message):
    return not message.pinned

async def purge_amount(ctx: Context[Pidroid], channel: MessageableGuildChannel, amount: int, check: Callable[[Message], bool]) -> list[Message]:
    """
    Purges a specified amount of messages from the specified channel.
    
    Performs input validation by throwing BadArgument exceptions.
    """
    if amount <= 0:
        raise BadArgument("That's not a valid amount!")

    # Evan proof
    if amount > 500:
        raise BadArgument("The maximum amount of messages I can purge at once is 500!")

    #await ctx.message.delete(delay=0)
    return await channel.purge(before=Object(id=ctx.message.id), limit=amount, check=check)

async def purge_after(ctx: Context[Pidroid], channel: MessageableGuildChannel, message_id: int, check: Callable[[Message], bool]) -> list[Message]:
    """
    Purges messages after a specified message ID from the specified channel.
    """
    return await channel.purge(before=Object(id=ctx.message.id), after=Object(id=message_id), check=check)

class ModerationCommandCog(commands.Cog):
    """This class implements cog which contains commands for moderation."""

    def __init__(self, client: Pidroid):
        super().__init__()
        self.client: Pidroid = client

    @commands.hybrid_group(
        name="purge",
        brief="Removes messages from the channel, that are not pinned.",
        info="""
        Removes messages from the channel, that are not pinned.
        The amount corresponds to the amount of messages to search.
        If a message is referenced, messages after it will be removed.
        """,
        usage='[amount]',
        category=ModerationCategory,
        invoke_without_command=True,
        fallback="any"
    )
    @commands.bot_has_permissions(manage_messages=True, send_messages=True)
    @command_checks.can_purge()
    @commands.guild_only()
    async def purge_command(self, ctx: Context[Pidroid], amount: int | None = None):
        if ctx.invoked_subcommand is None:

            if amount and ctx.message.reference and ctx.message.reference.message_id:
                raise BadArgument("You cannot purge by message amount and message reference!")

            message_id = None
            if ctx.message.reference and ctx.message.reference.message_id:
                message_id = ctx.message.reference.message_id

            if amount is None and message_id is None:
                raise BadArgument("Please specify the amount of messages to purge!")

            assert isinstance(ctx.channel, MessageableGuildChannelTuple)
            if message_id:
                deleted = await purge_after(ctx, ctx.channel, message_id, is_not_pinned)
            else:
                assert amount
                deleted = await purge_amount(ctx, ctx.channel, amount, is_not_pinned)
            _ = await ctx.send(f'Purged {len(deleted)} message(s)!', delete_after=2.0)

    @purge_command.command(
        name="user",
        brief="Removes a specified amount of messages sent by specified user, that are not pinned.",
        info="""
        Removes a specified amount of messages sent by specified user, that are not pinned.
        The amount corresponds to the amount of messages to search, not purge.
        If a message is referenced, messages after it will be removed.
        """,
        usage="<user> [amount]",
        category=ModerationCategory
    )
    @commands.bot_has_permissions(manage_messages=True, send_messages=True)
    @command_checks.can_purge()
    @commands.guild_only()
    async def purge_user_command(self, ctx: Context[Pidroid], member: Member, amount: int | None = None):
        def is_member(message: Message):
            return message.author.id == member.id and not message.pinned
        
        if amount and ctx.message.reference and ctx.message.reference.message_id:
            raise BadArgument("You cannot purge by message amount and message reference!")

        message_id = None
        if ctx.message.reference and ctx.message.reference.message_id:
            message_id = ctx.message.reference.message_id

        if amount is None and message_id is None:
            raise BadArgument("Please specify the amount of messages to purge!")

        assert isinstance(ctx.channel, MessageableGuildChannelTuple)
        if message_id:
            deleted = await purge_after(ctx, ctx.channel, message_id, is_member)
        else:
            assert amount
            deleted = await purge_amount(ctx, ctx.channel, amount, is_member)
        _ = await ctx.send(f'Purged {len(deleted)} message(s)!', delete_after=2.0)

    @commands.command(hidden=True)
    @commands.bot_has_permissions(manage_messages=True, send_messages=True, attach_files=True)
    @command_checks.is_junior_moderator(manage_messages=True)
    @commands.guild_only()
    async def deletethis(self, ctx: Context[Pidroid]):
        assert isinstance(ctx.channel, MessageableGuildChannelTuple)
        await ctx.message.delete(delay=0)
        _ = await ctx.channel.purge(limit=1)
        _ = await ctx.send(file=File(Resource('delete_this.png')))

    @commands.hybrid_command(
        name="suspend",
        brief='Immediately suspends member\'s ability to send messages for a week.',
        usage='<member>',
        category=ModerationCategory
    )
    @app_commands.describe(member="Member you are trying to suspend.")
    @commands.bot_has_permissions(manage_messages=True, send_messages=True, moderate_members=True)
    @command_checks.is_junior_moderator(moderate_members=True)
    @commands.guild_only()
    async def suspend_command(
        self,
        ctx: Context[Pidroid],
        member: Member
    ):
        assert ctx.guild
        assert isinstance(ctx.message.author, Member)
        assert isinstance(ctx.channel, MessageableGuildChannelTuple)
        
        conf = await self.client.fetch_guild_configuration(ctx.guild.id)
        
        if member.bot:
            raise BadArgument("You cannot suspend bots, that would be pointless.")

        if member.id == ctx.message.author.id:
            raise BadArgument("You cannot suspend yourself!")

        if member.top_role >= ctx.message.author.top_role:
            raise BadArgument("Specified member is above or shares the same role with you, you cannot suspend them!")

        if member.top_role > ctx.guild.me.top_role:
            raise BadArgument("Specified member is above me, I cannot suspend them!")

        if is_guild_moderator(member) and not conf.allow_to_punish_moderators:
            raise BadArgument("You cannot suspend a moderator!")

        t = Timeout2(
            api=self.client.api,
            guild=ctx.guild,
            target=member,
            moderator=ctx.author,
            reason="Suspended communications",
            date_expire=delta_to_datetime(timedelta(days=7))
        )
        c = await t.issue()
        title=f"Punishment Issued (Case #{c.case_id})",
        await ctx.reply(view=ReadonlyContainerView(
            container=ui.Container(
                ui.TextDisplay(f"### {title}\n{t.public_issue_message}"),
                accent_color=Color.red()
            ))
        )

async def setup(client: Pidroid):
    await client.add_cog(ModerationCommandCog(client))
