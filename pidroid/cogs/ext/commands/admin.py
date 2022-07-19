import discord

from discord import AllowedMentions
from discord.ext import commands # type: ignore
from discord.ext.commands.context import Context # type: ignore
from discord.ext.commands.errors import BadArgument # type: ignore
from discord.utils import escape_markdown
from typing import List

from client import Pidroid
from cogs.models.categories import AdministrationCategory, UtilityCategory
from cogs.utils.embeds import PidroidEmbed, SuccessEmbed
from cogs.utils.decorators import command_checks

SETUP_REASON = "Guild jail system setup"

class AdminCommands(commands.Cog): # type: ignore
    """This class implements cog which contains commands for administrators."""

    def __init__(self, client: Pidroid):
        self.client = client

    @commands.group( # type: ignore
        brief='Returns server configuration for Pidroid.',
        category=AdministrationCategory,
        invoke_without_command=True
    )
    @commands.has_permissions(administrator=True) # type: ignore
    @command_checks.guild_configuration_exists()
    @commands.guild_only() # type: ignore
    async def configuration(self, ctx: Context):
        if ctx.invoked_subcommand is None:
            guild = ctx.guild
            data = self.client.get_guild_configuration(guild.id)

            if data is None:
                raise BadArgument('No configuration was found for the server. Something went horribly wrong.')

            embed = PidroidEmbed(title=f'Displaying configuration for {escape_markdown(guild.name)}')

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
                embed.add_field(name='Mute role (deprecated)', value=mute_role.mention)

            log_channel = guild.get_channel(data.log_channel)
            if log_channel is not None:
                embed.add_field(name='Log channel', value=log_channel.mention)

            embed.add_field(name="Everyone can create tags?", value=data.public_tags)
            embed.add_field(name="Strict phishing protection?", value=data.strict_anti_phishing)

            embed.set_footer(text=f'To edit the configuration, view the available administration commands with {prefixes[0]}help administration.')
        await ctx.reply(embed=embed)

    @configuration.command(
        brief='Sets up server jail system automatically.\nConfiguration consists out of creating a jail channel, role and setting up the permissions.\nCan be used to automatically set channel permissions.\nRequires administrator permissions.',
        category=AdministrationCategory
    )
    @commands.bot_has_guild_permissions(manage_roles=True, manage_channels=True, send_messages=True) # type: ignore
    @commands.has_permissions(administrator=True) # type: ignore
    @commands.max_concurrency(number=1, per=commands.BucketType.guild) # type: ignore
    @command_checks.guild_configuration_exists()
    @commands.guild_only() # type: ignore
    async def setupjail(self, ctx: Context):
        # Create empty array where we will store setup log
        action_log: List[str] = []
        async with ctx.typing():

            # Check if jailed role already exists, if not, create it
            existing_jail_role = discord.utils.get(ctx.guild.roles, name="Jailed")
            if existing_jail_role is None:
                jail_role = await ctx.guild.create_role(
                    name='Jailed',
                    reason=SETUP_REASON
                )
                action_log.append(f"Created {jail_role.mention} role; you are recommended to update role position in the role list")
            else:
                jail_role = existing_jail_role
                action_log.append(f"Reused already existing {existing_jail_role.mention} role")
            
            # Store guild channels before creating a new one
            guild_channels = ctx.guild.channels

            # Do the same for jail channel
            existing_jail_channel = discord.utils.get(ctx.guild.channels, name="jail")
            if existing_jail_channel is None:
                jail_channel = await ctx.guild.create_text_channel(
                    'jail',
                    overwrites={
                        ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                        jail_role: discord.PermissionOverwrite(read_messages=True)
                    },
                    reason=SETUP_REASON
                )
                action_log.append(f"Created {jail_channel.mention} channel")
            else:
                jail_channel = existing_jail_channel
                action_log.append(f"Reused already existing {existing_jail_channel.mention} channel")

            # Update permissions
            cnt = 0
            for channel in guild_channels:
                perms = channel.permissions_for(jail_role)
                can_read = perms.read_messages
                can_everyone_read = channel.permissions_for(ctx.guild.default_role).read_messages
                if channel.id == jail_channel.id:
                    if not can_read:
                        await channel.set_permissions(jail_role, read_messages=True, reason=SETUP_REASON)
                    continue
                if can_read or not can_everyone_read: # Saves on API requests, does not know if everyone can see it or not
                    await channel.set_permissions(jail_role, read_messages=False, reason=SETUP_REASON)
                    cnt += 1
            if cnt > 0:
                action_log.append(f"Denied read messages permissions for {jail_role.mention} in {cnt} channels")

            # Acquire config and submit changes to the database
            config = self.client.get_guild_configuration(ctx.guild.id)
            assert config is not None

            config.jail_role = jail_role.id
            config.jail_channel = jail_channel.id
            await config._update()

        await ctx.reply("Jail system setup complete:\n- " + '\n- '.join(action_log), allowed_mentions=AllowedMentions(roles=False))

    @configuration.command(
        brief='Sets server jail channel.\nRequires administrator permissions.',
        usage='<jail channel>',
        category=AdministrationCategory
    )
    @commands.bot_has_guild_permissions(send_messages=True) # type: ignore
    @commands.has_permissions(manage_guild=True) # type: ignore
    @commands.max_concurrency(number=1, per=commands.BucketType.guild) # type: ignore
    @command_checks.guild_configuration_exists()
    @commands.guild_only() # type: ignore
    async def setjailchannel(self, ctx: Context, channel: discord.TextChannel):
        config = self.client.get_guild_configuration(ctx.guild.id)
        assert config is not None
        await config.update_jail_channel(channel)
        await ctx.reply(f'Jail channel set to {channel.mention}')

    @configuration.command(
        brief='Sets server jail role.\nRequires administrator permissions.',
        usage='<jail role>',
        category=AdministrationCategory
    )
    @commands.bot_has_guild_permissions(send_messages=True) # type: ignore
    @commands.has_permissions(manage_guild=True) # type: ignore
    @commands.max_concurrency(number=1, per=commands.BucketType.guild) # type: ignore
    @command_checks.guild_configuration_exists()
    @commands.guild_only() # type: ignore
    async def setjailrole(self, ctx: Context, role: discord.Role):
        config = self.client.get_guild_configuration(ctx.guild.id)
        assert config is not None
        await config.update_jail_role(role)
        await ctx.reply(f'Jail role set to {role.mention}', allowed_mentions=AllowedMentions(roles=False))

    @configuration.command(
        brief='Sets server log channel.\nRequires manage server permissions.',
        usage='<log channel>',
        category=AdministrationCategory
    )
    @commands.bot_has_guild_permissions(send_messages=True) # type: ignore
    @commands.has_permissions(manage_guild=True) # type: ignore
    @commands.max_concurrency(number=1, per=commands.BucketType.guild) # type: ignore
    @command_checks.guild_configuration_exists()
    @commands.guild_only() # type: ignore
    async def setlogchannel(self, ctx: Context, channel: discord.TextChannel):
        config = self.client.get_guild_configuration(ctx.guild.id)
        assert config is not None
        await config.update_log_channel(channel)
        await ctx.reply(f'Log channel set to {channel.mention}')

    @configuration.command(
        brief='Sets server bot prefix.\nRequires manage server permission.',
        usage='<prefix>',
        category=AdministrationCategory
    )
    @commands.bot_has_guild_permissions(send_messages=True) # type: ignore
    @commands.has_permissions(manage_guild=True) # type: ignore
    @commands.max_concurrency(number=1, per=commands.BucketType.guild) # type: ignore
    @command_checks.guild_configuration_exists()
    @commands.guild_only() # type: ignore
    async def setprefix(self, ctx: Context, prefix: str):
        if len(prefix) > 1:
            raise BadArgument("Prefix cannot be longer than a single character!")

        if prefix == "\\":
            raise BadArgument("Prefix cannot be a forbidden character!")

        config = self.client.get_guild_configuration(ctx.guild.id)
        assert config is not None

        await config.update_prefixes(prefix)

        await ctx.reply(embed=SuccessEmbed(f'My prefix set to \'{prefix}\''))

    @configuration.command(
        name="toggle-tags",
        brief='Allow or deny everyone from creating tags.\nRequires manage server permission.',
        usage='<true/false>',
        category=AdministrationCategory
    )
    @commands.bot_has_guild_permissions(send_messages=True) # type: ignore
    @commands.has_permissions(manage_guild=True) # type: ignore
    @commands.max_concurrency(number=1, per=commands.BucketType.guild) # type: ignore
    @command_checks.guild_configuration_exists()
    @commands.guild_only() # type: ignore
    async def toggle_tags(self, ctx: Context, allow_public: bool = None):
        config = self.client.get_guild_configuration(ctx.guild.id)
        assert config is not None

        if not allow_public:
            allow_public = not config.public_tags
        await config.update_public_tag_permission(allow_public)

        if allow_public:
            return await ctx.reply(embed=SuccessEmbed('Everyone can now create tags!'))
        await ctx.reply(embed=SuccessEmbed('Only members with manage messages permission can create tags now!'))

    @configuration.command(
        name="toggle-strict-protection",
        brief=(
            "Enable or disable strict anti-phishing protection.\n"
            "Strict means that exceeding a certain amount of anti-phishing violations will result in a 24 hour time-out."
        ),
        usage='<true/false>',
        category=AdministrationCategory
    )
    @commands.bot_has_guild_permissions(send_messages=True) # type: ignore# type: ignore
    @commands.has_permissions(manage_guild=True) # type: ignore
    @commands.max_concurrency(number=1, per=commands.BucketType.guild) # type: ignore
    @command_checks.guild_configuration_exists()
    @commands.guild_only() # type: ignore
    async def toggle_strict_protection(self, ctx: Context, strict: bool = None):
        config = self.client.get_guild_configuration(ctx.guild.id)
        assert config is not None

        if not strict:
            strict = not config.strict_anti_phishing
        await config.update_anti_phising_permission(strict)

        if strict:
            return await ctx.reply(embed=SuccessEmbed("Strict anti-phishing protection enabled!"))
        await ctx.reply(embed=SuccessEmbed("Strict anti-phishing protection disabled!"))

    @commands.command( # type: ignore
        brief='Returns current server bot prefix.',
        category=UtilityCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @command_checks.guild_configuration_exists()
    @commands.guild_only() # type: ignore
    async def prefix(self, ctx: Context):
        config = self.client.get_guild_configuration(ctx.guild.id)
        assert config is not None

        prefixes = config.prefixes or self.client.prefixes
        prefix_str = '**, **'.join(prefixes)

        await ctx.reply(f"My prefixes are: **{prefix_str}**")


async def setup(client: Pidroid):
    await client.add_cog(AdminCommands(client))
