import datetime
import discord
import pytz # type: ignore

from discord.ext import commands # type: ignore
from discord.ext.commands import Context # type: ignore
from discord.ext.commands.errors import MissingRequiredArgument, BadUnionArgument, UserNotFound
from discord.embeds import Embed
from discord.member import Member
from discord.role import Role
from discord.user import User
from discord.utils import escape_markdown, format_dt
from typing import Union, Optional
from typing_extensions import Annotated

from pidroid.client import Pidroid
from pidroid.cogs.handlers.error_handler import notify
from pidroid.models.categories import InformationCategory
from pidroid.utils import normalize_permission_name
from pidroid.utils.checks import is_guild_moderator, is_guild_administrator
from pidroid.utils.embeds import PidroidEmbed
from pidroid.utils.time import utcnow


class InfoCommands(commands.Cog): # type: ignore
    """This class implements a cog for various discord information commands."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client

    @commands.command( # type: ignore
        name='profile-avatar',
        brief='Displays the real profile picture of a user.',
        usage='[user]',
        category=InformationCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def profile_avatar_command(
        self,
        ctx: Context,
        user: Annotated[Optional[Union[Member, User]], Union[Member, User]] = None
    ):
        user = user or ctx.author
        embed = PidroidEmbed(title=f'{escape_markdown(user.name)}\'s avatar')
        if isinstance(user, discord.User):
            embed.set_image(url=user.display_avatar.with_size(4096).url) # type: ignore
        else:
            embed.set_image(url=user._user.display_avatar.with_size(4096).url) # type: ignore
        await ctx.reply(embed=embed)

    @profile_avatar_command.error
    async def on_profile_avatar_command_error(self, ctx: Context, error):
        if isinstance(error, BadUnionArgument):
            if error.param.name == "user":
                for _err in error.errors:
                    if isinstance(_err, UserNotFound):
                        return await notify(ctx, str(_err))
        setattr(error, 'unhandled', True)

    @commands.command( # type: ignore
        name='avatar',
        brief='Displays the server profile picture of a user.',
        usage='[user]',
        aliases=['server-avatar'],
        category=InformationCategory
    )
    @commands.guild_only() # type: ignore
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def server_avatar_command(
        self,
        ctx: Context,
        user: Annotated[Optional[Union[Member, User]], Union[Member, User]] = None
    ):
        user = user or ctx.author
        embed = PidroidEmbed(title=f'{escape_markdown(user.name)}\'s avatar')
        embed.set_image(url=user.display_avatar.with_size(4096).url) # type: ignore
        await ctx.reply(embed=embed)

    @server_avatar_command.error
    async def on_server_avatar_command_error(self, ctx: Context, error):
        if isinstance(error, BadUnionArgument):
            if error.param.name == "user":
                for _err in error.errors:
                    if isinstance(_err, UserNotFound):
                        return await notify(ctx, str(_err))
        setattr(error, 'unhandled', True)

    @commands.command( # type: ignore
        name='user-info',
        brief='Displays the user information.',
        usage='[user]',
        aliases=['ui', 'user', 'userinfo'],
        examples=[
            ("View your own information", 'user-info'),
            ("View information for Pidroid", 'user-info Pidroid'),
            (
                "View information for Pidroid Development",
                'user-info "Pidroid Development#8766"'
            )
        ],
        category=InformationCategory
    )
    @commands.guild_only() # type: ignore
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def user_info_command(
        self,
        ctx: Context,
        user: Annotated[Optional[Union[Member, User]], Union[Member, User]] = None
    ):
        user = user or ctx.author

        embed = PidroidEmbed(description=user.mention)
        embed.set_author(name=f'{user.name}#{user.discriminator}', icon_url=user.display_avatar.url)
        embed.add_field(name='Username', value=f'{escape_markdown(user.name)}#{user.discriminator}')
        embed.add_field(name='ID', value=user.id)
        embed.add_field(name='Registered', value=format_dt(user.created_at), inline=False)

        if isinstance(user, Member):

            assert ctx.guild is not None

            role_list = [role.mention for role in reversed(user.roles) if role.name != "@everyone"]

            # List roles
            role_count = len(role_list)
            roles = " ".join(role_list)
            if role_count == 0:
                roles = 'None'

            # Get server member bot acknowledgement
            if user.id == ctx.guild.owner_id:
                acknowledgement = 'Server Owner'
            elif is_guild_administrator(user):
                acknowledgement = 'Server Administrator'
            elif is_guild_moderator(user):
                acknowledgement = 'Server Moderator'
            else:
                acknowledgement = 'Server Member'

            # Get member permissions
            permissions = [permission[0] for permission in user.guild_permissions if permission[1]]
            for i, permission in enumerate(permissions):
                permissions[i] = normalize_permission_name(permission)

            if user.joined_at is not None:
                embed.add_field(name='Joined', value=format_dt(user.joined_at), inline=False)
            embed.add_field(name=f'Roles [{role_count:,}]', value=roles, inline=True)
            # Obtain join position, if possible
            if user.joined_at is not None:
                pos = sum(m.joined_at < user.joined_at for m in ctx.guild.members if m.joined_at is not None) + 1
                embed.add_field(name='Join Position', value=f'{pos:,}', inline=True)
            embed.add_field(name='Permissions', value=', '.join(permissions) + '.', inline=False)
            embed.add_field(name='Acknowledgements', value=acknowledgement, inline=False)

        embed.set_thumbnail(url=user.display_avatar.with_size(4096).url) # type: ignore
        await ctx.reply(embed=embed)

    @user_info_command.error
    async def on_user_info_command_error(self, ctx: Context, error):
        if isinstance(error, BadUnionArgument):
            if error.param.name == "user":
                for _err in error.errors:
                    if isinstance(_err, UserNotFound):
                        return await notify(ctx, str(_err))
        setattr(error, 'unhandled', True)

    @commands.command( # type: ignore
        name='server-info',
        brief='Displays the server information.',
        aliases=['si', 'serverinfo'],
        category=InformationCategory
    )
    @commands.guild_only() # type: ignore
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def server_info_command(self, ctx: Context):
        assert ctx.guild is not None
        guild = ctx.guild
        embed = PidroidEmbed(timestamp=guild.created_at)
        if guild.icon:
            embed.set_author(name=guild.name, icon_url=guild.icon.url)
            embed.set_thumbnail(url=guild.icon.with_size(4096).url) # type: ignore
        else:
            embed.set_author(name=guild.name)
        embed.add_field(name='Owner', value=guild.owner)
        embed.add_field(name='Channel Categories', value=f'{len(guild.categories):,}')
        embed.add_field(name='Text Channels', value=f'{len(guild.text_channels):,}')
        embed.add_field(name='Voice Channels', value=f'{len(guild.voice_channels):,}')
        embed.add_field(name='Members', value=f'{guild.member_count:,}')
        embed.add_field(name='Roles', value=f'{len(guild.roles):,}')
        embed.set_footer(text='Server created')
        await ctx.reply(embed=embed)

    @commands.command( # type: ignore
        name='role-info',
        brief='Displays the role information.',
        aliases=['ri', 'roleinfo'],
        examples=[
            ("Display information for Plugin expert role", 'role-info "Plugin expert"'),
            ("You can also just use the mention, although not recommended", 'role-info @Plugin expert'),
        ],
        category=InformationCategory
    )
    @commands.guild_only() # type: ignore
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def role_info_command(self, ctx: Context, role: Role):
        embed = Embed(description=role.mention, timestamp=role.created_at, colour=role.colour)
        if role.icon:
            embed.set_thumbnail(url=role.icon.with_size(4096).url) # type: ignore
        embed.add_field(name="Name", value=role.name)
        embed.add_field(name="ID", value=role.id)
        embed.add_field(name="Position", value=role.position)
        embed.add_field(name="Colour", value=str(role.colour))
        embed.add_field(name="Is mentionable", value=role.mentionable)
        embed.set_footer(text="Role created")
        await ctx.reply(embed=embed)

    @role_info_command.error
    async def on_role_info_command_error(self, ctx: Context, error):
        if isinstance(error, MissingRequiredArgument):
            if error.param.name == "role":
                return await notify(ctx, "Please specify the role to view the information for.")
        setattr(error, 'unhandled', True)

    @commands.command( # type: ignore
        brief='Displays time information across the globe.',
        category=InformationCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def time(self, ctx: Context):
        def stringify(date: datetime.datetime):
            return date.strftime("%d %B %Y %H:%M")

        utc = utcnow()
        cet = utc.astimezone(pytz.timezone("CET"))
        pt = utc.astimezone(pytz.timezone("US/Pacific"))
        ny = utc.astimezone(pytz.timezone("America/New_York"))
        ist = utc.astimezone(pytz.timezone("Asia/Kolkata"))
        ja = utc.astimezone(pytz.timezone("Japan"))

        embed = PidroidEmbed(title="Displaying different times across the globe")
        embed.add_field(name="Pacific Time", value=stringify(pt))
        embed.add_field(name="Eastern Standard Time", value=stringify(ny))
        embed.add_field(name="Coordinated Universal Time", value=stringify(utc))
        embed.add_field(name="Central European Time", value=stringify(cet))
        embed.add_field(name="Indian Standard Time", value=stringify(ist))
        embed.add_field(name="Japanese Standard Time", value=stringify(ja))

        embed.add_field(name="Your time", value=format_dt(utc))
        await ctx.reply(embed=embed)

async def setup(client: Pidroid) -> None:
    await client.add_cog(InfoCommands(client))
