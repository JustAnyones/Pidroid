from discord.ext import commands
from discord.ext.commands import BadArgument, Context
from discord.utils import escape_markdown

from pidroid.client import Pidroid
from pidroid.models.categories import AdministrationCategory
from pidroid.utils.embeds import PidroidEmbed

class AdminCommands(commands.Cog):
    """This class implements cog which contains commands for administrators."""

    def __init__(self, client: Pidroid):
        self.client = client

    @commands.group(
        brief='DEPRECATED: Returns server configuration for Pidroid.',
        category=AdministrationCategory,
        invoke_without_command=True
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def configuration(self, ctx: Context):
        assert ctx.guild is not None
        if ctx.invoked_subcommand is None:
            guild = ctx.guild
            data = await self.client.fetch_guild_configuration(guild.id)

            embed = PidroidEmbed(title=f'Displaying configuration for {escape_markdown(guild.name)}')
            embed.description = "WARNING: this command is deprecated and will be removed in the future"

            prefixes = data.prefixes or self.client.prefixes
            embed.add_field(name='Prefixes', value=', '.join(prefixes))

            if data.jail_role_id:
                jail_role = await self.client.get_or_fetch_role(guild, data.jail_role_id)
                if jail_role is not None:
                    embed.add_field(name='Jail role', value=jail_role.mention)

            if data.jail_channel_id:
                jail_channel = await self.client.get_or_fetch_guild_channel(guild, data.jail_channel_id)
                if jail_channel is not None:
                    embed.add_field(name='Jail channel', value=jail_channel.mention)
            
            if data.logging_channel_id:
                log_channel = await self.client.get_or_fetch_guild_channel(guild, data.logging_channel_id)
                if log_channel is not None:
                    embed.add_field(name='Log channel', value=log_channel.mention)

            embed.add_field(name="Can everyone manage tags?", value="Yes" if data.public_tags else "No")

            embed.set_footer(text=f'To edit the configuration, view the available administration commands with {prefixes[0]}help administration.')
            await ctx.reply(embed=embed)

    @configuration.command( # type: ignore
        brief='Sets up server jail system automatically.\nConfiguration consists out of creating a jail channel, role and setting up the permissions.\nCan be used to automatically set channel permissions.\nRequires administrator permissions.',
        category=AdministrationCategory,
        hidden=True
    )
    @commands.bot_has_guild_permissions(manage_roles=True, manage_channels=True, send_messages=True)
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def setupjail(self, ctx: Context):
        raise BadArgument(f"Command has been replaced by {ctx.prefix}configure setup-jail-system.")

    @configuration.command( # type: ignore
        brief='Sets server jail channel.\nRequires administrator permissions.',
        usage='<jail channel>',
        category=AdministrationCategory,
        hidden=True
    )
    @commands.bot_has_guild_permissions(send_messages=True)
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def setjailchannel(self, ctx: Context):
        raise BadArgument(f"Command has been replaced by {ctx.prefix}configure.")

    @configuration.command( # type: ignore
        brief='Sets server jail role.\nRequires administrator permissions.',
        usage='<jail role>',
        category=AdministrationCategory,
        hidden=True
    )
    @commands.bot_has_guild_permissions(send_messages=True)
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def setjailrole(self, ctx: Context):
        raise BadArgument(f"Command has been replaced by {ctx.prefix}configure.")

    @configuration.command( # type: ignore
        brief='Sets server bot prefix.\nRequires manage server permission.',
        usage='<prefix>',
        category=AdministrationCategory,
        hidden=True
    )
    @commands.bot_has_guild_permissions(send_messages=True)
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def setprefix(self, ctx: Context):
        raise BadArgument(f"Command has been replaced by {ctx.prefix}configure.")

    @configuration.command( # type: ignore
        name="toggle-tags",
        brief='Allow or deny everyone from creating tags.\nRequires manage server permission.',
        usage='<true/false>',
        category=AdministrationCategory,
        hidden=True
    )
    @commands.bot_has_guild_permissions(send_messages=True)
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def toggle_tags(self, ctx: Context):
        raise BadArgument(f"Command has been replaced by {ctx.prefix}configure.")

async def setup(client: Pidroid):
    await client.add_cog(AdminCommands(client))
