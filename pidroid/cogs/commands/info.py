import datetime
import discord
import pytz # type: ignore

from discord.ext import commands # type: ignore
from discord.ext.commands import Context # type: ignore
from discord.ext.commands.errors import MissingRequiredArgument
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
        brief='Displays the real profile picture of a specified member.',
        usage='[member]',
        category=InformationCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def profile_avatar(
        self,
        ctx: Context,
        member: Annotated[Optional[Union[Member, User]], Union[Member, User]] = None
    ):
        member = member or ctx.author
        embed = PidroidEmbed(title=f'{escape_markdown(member.name)}\'s avatar')
        if isinstance(member, discord.User):
            embed.set_image(url=member.display_avatar.with_size(4096).url) # type: ignore
        else:
            embed.set_image(url=member._user.display_avatar.with_size(4096).url) # type: ignore
        await ctx.reply(embed=embed)

    @commands.command( # type: ignore
        name='avatar',
        brief='Displays the server profile picture of a specified member.',
        usage='[member]',
        aliases=['server-avatar'],
        category=InformationCategory
    )
    @commands.guild_only() # type: ignore
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def server_avatar(
        self,
        ctx: Context,
        member: Annotated[Optional[Union[Member, User]], Union[Member, User]] = None
    ):
        member = member or ctx.author
        embed = PidroidEmbed(title=f'{escape_markdown(member.name)}\'s avatar')
        embed.set_image(url=member.display_avatar.with_size(4096).url) # type: ignore
        await ctx.reply(embed=embed)

    @commands.command( # type: ignore
        name='user-info',
        brief='Displays the user information of a specified member.',
        usage='[member]',
        aliases=['ui', 'user', 'userinfo'],
        category=InformationCategory
    )
    @commands.guild_only() # type: ignore
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def user_info(
        self,
        ctx: Context,
        member: Annotated[Optional[Union[Member, User]], Union[Member, User]] = None
    ):
        member = member or ctx.author

        embed = PidroidEmbed(description=member.mention)
        embed.set_author(name=f'{member.name}#{member.discriminator}', icon_url=member.display_avatar.url)
        embed.add_field(name='Username', value=f'{escape_markdown(member.name)}#{member.discriminator}')
        embed.add_field(name='ID', value=member.id)
        embed.add_field(name='Registered', value=format_dt(member.created_at), inline=False)

        if isinstance(member, Member):

            assert ctx.guild is not None

            role_list = [role.mention for role in reversed(member.roles) if role.name != "@everyone"]

            # List roles
            role_count = len(role_list)
            roles = " ".join(role_list)
            if role_count == 0:
                roles = 'None'

            # Get server member bot acknowledgement
            if member.id == ctx.guild.owner_id:
                acknowledgement = 'Server Owner'
            elif is_guild_administrator(member):
                acknowledgement = 'Server Administrator'
            elif is_guild_moderator(member):
                acknowledgement = 'Server Moderator'
            else:
                acknowledgement = 'Server Member'

            # Get member permissions
            permissions = [permission[0] for permission in member.guild_permissions if permission[1]]
            for i, permission in enumerate(permissions):
                permissions[i] = normalize_permission_name(permission)

            if member.joined_at is not None:
                embed.add_field(name='Joined', value=format_dt(member.joined_at), inline=False)
            embed.add_field(name=f'Roles [{role_count:,}]', value=roles, inline=True)
            # Obtain join position, if possible
            if member.joined_at is not None:
                pos = sum(m.joined_at < member.joined_at for m in ctx.guild.members if m.joined_at is not None) + 1
                embed.add_field(name='Join Position', value=f'{pos:,}', inline=True)
            embed.add_field(name='Permissions', value=', '.join(permissions) + '.', inline=False)
            embed.add_field(name='Acknowledgements', value=acknowledgement, inline=False)

        embed.set_thumbnail(url=member.display_avatar.with_size(4096).url) # type: ignore
        await ctx.reply(embed=embed)

    @commands.command( # type: ignore
        name='server-info',
        brief='Displays the server information.',
        aliases=['si', 'serverinfo'],
        category=InformationCategory
    )
    @commands.guild_only() # type: ignore
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def server_info(self, ctx: Context):
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
        category=InformationCategory
    )
    @commands.guild_only() # type: ignore
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def role_info(self, ctx: Context, role: Role):
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

    @role_info.error
    async def on_role_info_command_error(self, ctx: Context, error):
        if isinstance(error, MissingRequiredArgument):
            if error.param.name == "role":
                return await notify(ctx, "Please specify the role to view the information for")
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
