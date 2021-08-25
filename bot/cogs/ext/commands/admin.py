import discord

from discord import AllowedMentions
from discord.channel import TextChannel
from discord.ext import commands
from discord.ext.commands.context import Context
from discord.guild import Guild
from discord.role import Role
from discord.utils import escape_markdown
from typing import List, Tuple

from client import Pidroid
from cogs.models.categories import AdministrationCategory, UtilityCategory
from cogs.utils.embeds import build_embed, error, success

SETUP_REASON = "Guild configuration setup"

class AdminCommands(commands.Cog):
    """This class implements cog which contains commands for administrators."""

    def __init__(self, client: Pidroid):
        self.client = client
        self.api = self.client.api

    async def setup_jail_system(self, ctx: Context, channels: List[TextChannel]) -> Tuple[Role, TextChannel]:
        """Creates a jail channel and a role. Disables ability to read any channel but the jail."""
        guild: Guild = ctx.guild
        jail_role = await guild.create_role(
            name='Jailed',
            reason=SETUP_REASON
        )
        jail_channel = await guild.create_text_channel(
            'jail',
            overwrites={
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                jail_role: discord.PermissionOverwrite(read_messages=True)
            },
            reason=SETUP_REASON
        )
        for channel in channels:
            await channel.set_permissions(jail_role, read_messages=False, reason=SETUP_REASON)
        return jail_role, jail_channel

    async def setup_mute_system(self, ctx: Context, channels: List[TextChannel]) -> Role:
        """Creates muted role. Disables ability send messages in any channel."""
        mute_role = await ctx.guild.create_role(
            name='Muted',
            permissions=discord.Permissions(send_messages=False),
            reason=SETUP_REASON
        )
        for channel in channels:
            await channel.set_permissions(mute_role, send_messages=False, reason=SETUP_REASON)
        return mute_role

    @commands.group(
        brief='Returns bot server configuration.',
        category=AdministrationCategory,
        invoke_without_command=True
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def configuration(self, ctx: Context):
        if not self.client.guild_config_cache_ready:
            return

        if ctx.invoked_subcommand is None:
            guild = ctx.guild
            data = self.client.get_guild_configuration(guild.id)

            if data is None:
                return await ctx.reply(
                    embed=error(
                        'No configuration was found for the server. '
                        f'You can create one by running ``{self.client.prefix}configuration setup`` command.'
                    ))

            embed = build_embed(title=f'Displaying configuration for {escape_markdown(guild.name)}')

            prefixes = data.prefixes or self.client.prefixes
            embed.add_field(name='Prefixes', value=', '.join(prefixes))

            jail_role = guild.get_role(data.jail_role)
            if jail_role is not None:
                embed.add_field(name='Jail role', value=jail_role.mention)

            jail_channel = guild.get_channel(data.jail_channel)
            if jail_channel is not None:
                embed.add_field(name='Jail channel', value=jail_channel.mention)

            mute_role = guild.get_role(data.mute_role)
            if mute_role is not None:
                embed.add_field(name='Mute role', value=mute_role.mention)

            embed.set_footer(text=f'To edit the configuration, view administration category with {self.client.prefix}help administration.')
        await ctx.reply(embed=embed)

    @configuration.command(
        brief='Sets up server configuration automatically.\nConfiguration consists out of creating channels and roles required for moderation functionality of the bot.\nRequires administrator permissions.',
        category=AdministrationCategory
    )
    @commands.bot_has_guild_permissions(manage_roles=True, manage_channels=True, send_messages=True)
    @commands.max_concurrency(number=1, per=commands.BucketType.guild)
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def setup(self, ctx: Context):
        if not self.client.guild_config_cache_ready:
            return

        guild: Guild = ctx.guild
        guild_channels = guild.channels

        if guild.id in self.client.guild_configuration_guilds:
            return await ctx.reply(embed=error(
                'Configuration already exists! If you want to edit the configuration, use other subcommands.'
            ))

        jail_role, jail_channel = await self.setup_jail_system(ctx, guild_channels)
        mute_role = await self.setup_mute_system(ctx, guild_channels)

        config = await self.api.create_new_guild_configuration(guild.id, jail_channel.id, jail_role.id, mute_role.id)
        self.client._update_guild_configuration(ctx.guild.id, config)
        await ctx.reply('Configuration complete')
        await ctx.invoke(self.client.get_command('configuration'))

    @configuration.command(
        brief='Sets server jail channel.\nRequires administrator permissions.',
        usage='<jail channel>',
        category=AdministrationCategory
    )
    @commands.bot_has_guild_permissions(send_messages=True)
    @commands.max_concurrency(number=1, per=commands.BucketType.guild)
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def setjail(self, ctx: Context, channel: discord.TextChannel):
        if not self.client.guild_config_cache_ready:
            return
        config = self.client.get_guild_configuration(ctx.guild.id)
        await config.update_jail_channel(channel)
        await ctx.reply(f'Jail channel set to {channel.mention}')

    @configuration.command(
        brief='Sets server jail role.\nRequires administrator permissions.',
        usage='<jail role>',
        category=AdministrationCategory
    )
    @commands.bot_has_guild_permissions(send_messages=True)
    @commands.max_concurrency(number=1, per=commands.BucketType.guild)
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def setjailrole(self, ctx: Context, role: discord.Role):
        if not self.client.guild_config_cache_ready:
            return
        config = self.client.get_guild_configuration(ctx.guild.id)
        await config.update_jail_role(role)
        await ctx.reply(f'Jail role set to {role.mention}', allowed_mentions=AllowedMentions(roles=False))

    @configuration.command(
        brief='Sets server mute role.\nRequires administrator permissions.',
        usage='<mute role>',
        category=AdministrationCategory
    )
    @commands.bot_has_guild_permissions(send_messages=True)
    @commands.max_concurrency(number=1, per=commands.BucketType.guild)
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def setmuterole(self, ctx: Context, role: discord.Role):
        if not self.client.guild_config_cache_ready:
            return
        config = self.client.get_guild_configuration(ctx.guild.id)
        await config.update_mute_role(role)
        await ctx.reply(f'Mute role set to {role.mention}', allowed_mentions=AllowedMentions(roles=False))

    @configuration.command(
        brief='Sets server bot prefix.\nRequires manage server permission.',
        usage='<prefix>',
        category=AdministrationCategory
    )
    @commands.bot_has_guild_permissions(send_messages=True)
    @commands.max_concurrency(number=1, per=commands.BucketType.guild)
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def setprefix(self, ctx: Context, prefix: str):
        if not self.client.guild_config_cache_ready:
            return

        if len(prefix) > 1:
            return await ctx.reply(embed=error("Prefix cannot be longer than a single character!"))

        if prefix == "\\":
            return await ctx.reply(embed=error("Prefix cannot be a forbidden character!"))

        config = self.client.get_guild_configuration(ctx.guild.id)
        await config.update_prefix(prefix)

        await ctx.reply(embed=success(f'My prefix set to \'{prefix}\''))

    @commands.command(
        brief='Retrieves all custom emojis from a referenced message.',
        category=UtilityCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    async def prefix(self, ctx: Context):
        if not self.client.guild_config_cache_ready:
            return

        config = self.client.get_guild_configuration(ctx.guild.id)

        prefixes = config.prefixes or self.client.prefixes
        prefix_str = '**, **'.join(prefixes)

        await ctx.reply(f"My prefixes are: **{prefix_str}**")


def setup(client: Pidroid):
    client.add_cog(AdminCommands(client))
