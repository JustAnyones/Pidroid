import datetime
import discord
import pytz

from discord.embeds import Embed
from discord.ext import commands
from discord.ext.commands import BadArgument, BadUnionArgument, Context, MissingRequiredArgument, UserNotFound
from discord.member import Member
from discord.role import Role
from discord.utils import escape_markdown, format_dt
from typing import override
from typing_extensions import Annotated

from pidroid.client import Pidroid
from pidroid.models.categories import InformationCategory
from pidroid.models.view import PaginatingView
from pidroid.services.error_handler import notify
from pidroid.utils import normalize_permission_name
from pidroid.utils.aliases import DiscordUser
from pidroid.utils.checks import is_guild_moderator, is_guild_administrator
from pidroid.utils.embeds import PidroidEmbed
from pidroid.utils.paginators import ListPageSource
from pidroid.utils.time import utcnow

class RolePaginator(ListPageSource):
    def __init__(self, title: str, data: list[Role]):
        super().__init__(data, per_page=20)
        self.embed = PidroidEmbed(title=title)
        role_count = len(data)
        if role_count == 1:
            _ = self.embed.set_footer(text=f"1 role")
        else:
            _ = self.embed.set_footer(text=f"{role_count} roles")

    @override
    async def format_page(self, menu: PaginatingView, page: list[Role]):
        offset = menu.current_page * self.per_page + 1
        values = ""
        for i, role in enumerate(page):
            member_count = len(role.members)
            if member_count == 1:
                count = "1 member"
            elif member_count > 1:
                count = f"{member_count} members"
            else:
                count = "no members"
            values += f"{i + offset}. {role.mention} ({count})\n"
        self.embed.description = values.strip()
        return self.embed

class InformationCommandCog(commands.Cog):
    """This class implements a cog for various discord information commands."""

    def __init__(self, client: Pidroid) -> None:
        super().__init__()
        self.client = client

    @commands.command(
        name='profile-avatar',
        brief='Displays the real profile picture of a user.',
        usage='[user]',
        category=InformationCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    async def profile_avatar_command(
        self,
        ctx: Context[Pidroid],
        user: Annotated[DiscordUser | None, DiscordUser] = None
    ):
        user = user or ctx.author
        embed = PidroidEmbed(title=f'{escape_markdown(user.name)}\'s avatar')
        if isinstance(user, discord.User):
            _ = embed.set_image(url=user.display_avatar.with_size(4096).url)
        else:
            _ = embed.set_image(url=user._user.display_avatar.with_size(4096).url)
        return await ctx.reply(embed=embed)

    @profile_avatar_command.error
    async def on_profile_avatar_command_error(self, ctx: Context[Pidroid], error: Exception):
        if isinstance(error, BadUnionArgument):
            if error.param.name == "user":
                for _err in error.errors:
                    if isinstance(_err, UserNotFound):
                        return await notify(ctx, str(_err))
        setattr(error, 'unhandled', True)

    @commands.command(
        name='avatar',
        brief='Displays the server profile picture of a user.',
        usage='[user]',
        aliases=['server-avatar'],
        category=InformationCategory
    )
    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    async def server_avatar_command(
        self,
        ctx: Context[Pidroid],
        user: Annotated[DiscordUser | None, DiscordUser] = None
    ):
        user = user or ctx.author
        embed = PidroidEmbed(title=f'{escape_markdown(user.name)}\'s avatar')
        _ = embed.set_image(url=user.display_avatar.with_size(4096).url)
        return await ctx.reply(embed=embed)

    @server_avatar_command.error
    async def on_server_avatar_command_error(self, ctx: Context[Pidroid], error: Exception):
        if isinstance(error, BadUnionArgument):
            if error.param.name == "user":
                for _err in error.errors:
                    if isinstance(_err, UserNotFound):
                        return await notify(ctx, str(_err))
        setattr(error, 'unhandled', True)

    @commands.command(
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
    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    async def user_info_command(
        self,
        ctx: Context[Pidroid],
        user: Annotated[DiscordUser | None, DiscordUser] = None
    ):
        user = user or ctx.author

        embed = PidroidEmbed(description=user.mention)
        embed.set_author(name=str(user), icon_url=user.display_avatar.url)
        embed.add_field(name='Username', value=f'{escape_markdown(str(user))}')
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

        embed.set_thumbnail(url=user.display_avatar.with_size(4096).url)
        await ctx.reply(embed=embed)

    @user_info_command.error
    async def on_user_info_command_error(self, ctx: Context[Pidroid], error: Exception):
        if isinstance(error, BadUnionArgument):
            if error.param.name == "user":
                for _err in error.errors:
                    if isinstance(_err, UserNotFound):
                        return await notify(ctx, str(_err))
        setattr(error, 'unhandled', True)

    @commands.command(
        name='server-info',
        brief='Displays the server information.',
        aliases=['si', 'serverinfo'],
        category=InformationCategory
    )
    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    async def server_info_command(self, ctx: Context[Pidroid]):
        assert ctx.guild is not None
        guild = ctx.guild
        embed = PidroidEmbed(timestamp=guild.created_at)
        if guild.icon:
            _ = (embed
                .set_author(name=guild.name, icon_url=guild.icon.url)
                .set_thumbnail(url=guild.icon.with_size(4096).url)
            )
        else:
            _ = embed.set_author(name=guild.name)
        _ = (embed
            .add_field(name='Owner', value=guild.owner)
            .add_field(name='Channel Categories', value=f'{len(guild.categories):,}')
            .add_field(name='Text Channels', value=f'{len(guild.text_channels):,}')
            .add_field(name='Voice Channels', value=f'{len(guild.voice_channels):,}')
            .add_field(name='Members', value=f'{guild.member_count:,}')
            .add_field(name='Roles', value=f'{len(guild.roles):,}')
            .set_footer(text='Server created')
        )
        return await ctx.reply(embed=embed)

    @commands.command(
        name='role-info',
        brief='Displays the role information.',
        aliases=['ri', 'roleinfo'],
        examples=[
            ("Display information for Plugin expert role", 'role-info "Plugin expert"'),
            ("You can also just use the mention, although not recommended", 'role-info @Plugin expert'),
        ],
        category=InformationCategory
    )
    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    async def role_info_command(self, ctx: Context[Pidroid], role: Role):
        embed = Embed(description=role.mention, timestamp=role.created_at, colour=role.colour)
        if role.icon:
            _ = embed.set_thumbnail(url=role.icon.with_size(4096).url)
        _ = (embed
            .add_field(name="Name", value=role.name)
            .add_field(name="ID", value=role.id)
            .add_field(name="Position", value=role.position)
            .add_field(name="Colour", value=str(role.colour))
            .add_field(name="Is mentionable", value=role.mentionable)
            .set_footer(text="Role created")
        )
        return await ctx.reply(embed=embed)

    @role_info_command.error
    async def on_role_info_command_error(self, ctx: Context[Pidroid], error: Exception):
        if isinstance(error, MissingRequiredArgument):
            if error.param.name == "role":
                return await notify(ctx, "Please specify the role to view the information for.")
        setattr(error, 'unhandled', True)

    @commands.command(
        name='roles',
        brief='Displays a list of server roles.',
        aliases=['role-list'],
        category=InformationCategory
    )
    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def roles_command(self, ctx: Context[Pidroid]):
        assert ctx.guild

        roles = [
            r for r in reversed(ctx.guild.roles) if r.name != "@everyone"
        ]

        if not roles:
            raise BadArgument("This server does not have any roles")

        view = PaginatingView(client=self.client, ctx=ctx, source=RolePaginator(
            f"Roles in {ctx.guild.name}",
            roles
        ))
        await view.send()

    @commands.command(
        brief='Displays time information across the globe.',
        category=InformationCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    async def time(self, ctx: Context[Pidroid]):
        def stringify(date: datetime.datetime):
            return date.strftime("%d %B %Y %H:%M")

        utc = utcnow()
        cet = utc.astimezone(pytz.timezone("CET"))
        pt = utc.astimezone(pytz.timezone("US/Pacific"))
        ny = utc.astimezone(pytz.timezone("America/New_York"))
        ist = utc.astimezone(pytz.timezone("Asia/Kolkata"))
        ja = utc.astimezone(pytz.timezone("Japan"))

        embed = PidroidEmbed(title="Displaying different times across the globe")
        _ = (embed
            .add_field(name="Pacific Time", value=stringify(pt))
            .add_field(name="Eastern Standard Time", value=stringify(ny))
            .add_field(name="Coordinated Universal Time (GMT)", value=stringify(utc))
            .add_field(name="Central European Time", value=stringify(cet))
            .add_field(name="Indian Standard Time", value=stringify(ist))
            .add_field(name="Japanese Standard Time", value=stringify(ja))
            .add_field(name="Your time", value=format_dt(utc))
        )
        return await ctx.reply(embed=embed)

async def setup(client: Pidroid) -> None:
    await client.add_cog(InformationCommandCog(client))
