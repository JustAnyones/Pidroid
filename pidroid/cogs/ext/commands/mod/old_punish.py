import discord

from discord.ext import commands
from discord.ext.commands.context import Context # type: ignore

from pidroid.client import Pidroid
from pidroid.cogs.models.case import Mute
from pidroid.cogs.models.categories import ModerationCategory
from pidroid.cogs.utils.converters import MemberOffender
from pidroid.cogs.utils.decorators import command_checks
from pidroid.cogs.utils.embeds import ErrorEmbed
from pidroid.cogs.utils.getters import get_role

class OldModeratorCommands(commands.Cog): # type: ignore
    """This class implements cog which contains commands for moderation."""

    def __init__(self, client: Pidroid):
        self.client = client

    @commands.command( # type: ignore
        brief='DEPRECATED: Unmutes specified member.',
        usage='<member>',
        category=ModerationCategory
    )
    @commands.bot_has_permissions(manage_messages=True, send_messages=True, manage_roles=True) # type: ignore
    @command_checks.is_junior_moderator(kick_members=True)
    @command_checks.guild_configuration_exists()
    @commands.guild_only() # type: ignore
    async def unmute(self, ctx: Context, *, member: MemberOffender):
        c = self.client.get_guild_configuration(ctx.guild.id)
        assert c is not None

        role = get_role(ctx.guild, c.mute_role)
        if role is None:
            return await ctx.reply(embed=ErrorEmbed("Mute role not found, cannot remove!"))

        if discord.utils.get(ctx.guild.roles, id=role.id) not in member.roles:
            return await ctx.reply(embed=ErrorEmbed("The user is not muted!"))

        m = Mute(ctx, member)
        await m.revoke(role)
        await ctx.message.delete(delay=0)

async def setup(client: Pidroid):
    await client.add_cog(OldModeratorCommands(client))
