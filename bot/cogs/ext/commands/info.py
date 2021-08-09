import discord
import typing

from discord.asset import Asset
from discord.ext import commands
from discord.ext.commands import Context
from discord.guild import Guild
from discord.utils import escape_markdown, format_dt

from client import Pidroid
from cogs.models.categories import InformationCategory
from cogs.utils.checks import is_guild_moderator, is_guild_administrator
from cogs.utils.embeds import build_embed

def _from_guild_avatar(state, guild_id: int, member_id: int, avatar: str) -> Asset:
    animated = avatar.startswith('a_')
    format = 'gif' if animated else 'png'
    return Asset(
        state,
        url=f"{Asset.BASE}/guilds/{guild_id}/users/{member_id}/avatars/{avatar}.{format}?size=1024",
        key=avatar,
        animated=animated,
    )

class InfoCommands(commands.Cog):
    """This class implements a cog for various discord information commands."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client

    @commands.command(
        name='profile-avatar',
        brief='Displays the real profile picture of a specified member.',
        usage='[member]',
        category=InformationCategory
    )
    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    async def profile_avatar(self, ctx: Context, *, member: typing.Union[discord.Member, discord.User] = None):
        member = member or ctx.author
        embed = build_embed(title=f'{escape_markdown(member.name)}\'s avatar')
        embed.set_image(url=member.avatar.with_size(4096).url)
        await ctx.reply(embed=embed)

    @commands.command(
        name='avatar',
        brief='Displays the server profile picture of a specified member.',
        usage='[member]',
        aliases=['server-avatar'],
        category=InformationCategory
    )
    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    async def server_avatar(self, ctx: Context, *, member: typing.Union[discord.Member, discord.User] = None):
        member = member or ctx.author

        if isinstance(member, discord.Member):
            # VERY HACKY SOLUTION, REFACTOR WHEN DISCORD.PY 2.0 IMPLEMENTS PROPER METHOD
            user_data = await self.client._get_state().http.get_member(ctx.guild.id, member.id)

            if user_data["avatar"] is None:
                await ctx.invoke(self.client.get_command('profile-avatar'), member=member)

            else:
                avatar_url = _from_guild_avatar(self.client._get_state(), ctx.guild.id, member.id, user_data["avatar"]).with_size(4096).url

                embed = build_embed(title=f'{escape_markdown(member.name)}\'s avatar')
                embed.set_image(url=avatar_url)
                await ctx.send(embed=embed)
        else:
            await ctx.invoke(self.client.get_command('profile-avatar'), member=member)


    @commands.command(
        name='user-info',
        brief='Displays the user information of a specified member.',
        usage='[member]',
        aliases=['ui', 'user', 'userinfo'],
        category=InformationCategory
    )
    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    async def user_info(self, ctx: Context, *, member: typing.Union[discord.Member, discord.User] = None):
        member = member or ctx.author
        is_user = isinstance(member, discord.User)

        embed = build_embed(description=member.mention)
        embed.set_author(name=f'{member.name}#{member.discriminator}', icon_url=member.avatar.url)
        embed.add_field(name='Username', value=f'{escape_markdown(member.name)}#{member.discriminator}')
        embed.add_field(name='ID', value=member.id)
        embed.add_field(name='Registered', value=format_dt(member.created_at), inline=False)
        if not is_user:
            embed.add_field(name='Joined', value=format_dt(member.joined_at), inline=False)

        if not is_user:

            roleList = member.roles
            roleList.reverse()
            roles = []
            for role in roleList:
                if role.name == '@everyone': continue
                roles.append(role.mention)

            # List roles
            roleCount = len(roles)
            roles = " ".join(roles)
            if roleCount == 0:
                roles = 'None'

            # Get server member bot acknowledgement
            if member.id == ctx.guild.owner_id:
                acknowledgement = 'Server Owner'
            elif is_guild_administrator(ctx.guild, ctx.channel, member):
                acknowledgement = 'Server Administrator'
            elif is_guild_moderator(ctx.guild, ctx.channel, member):
                acknowledgement = 'Server Moderator'
            else:
                acknowledgement = 'Server Member'

            # Get member permissions
            permissions = [permission[0] for permission in member.guild_permissions if permission[1]]
            for i, permission in enumerate(permissions):
                permissions[i] = permission.replace('_', ' ').replace('guild', 'server').title().replace('Tts', 'TTS')

            # Get join position
            pos = sum(m.joined_at < member.joined_at for m in ctx.guild.members if m.joined_at is not None) + 1

            embed.add_field(name=f'Roles [{roleCount:,}]', value=roles, inline=True)
            embed.add_field(name='Join Position', value=f'{pos:,}', inline=True)
            embed.add_field(name='Permissions', value=', '.join(permissions) + '.', inline=False)
            embed.add_field(name='Acknowledgements', value=acknowledgement, inline=False)

        embed.set_thumbnail(url=member.avatar.with_size(4096).url)
        await ctx.reply(embed=embed)

    @commands.command(
        name='server-info',
        brief='Displays the server information.',
        aliases=['si', 'serverinfo'],
        category=InformationCategory
    )
    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    async def server_info(self, ctx: Context):
        guild: Guild = ctx.guild
        embed = build_embed(timestamp=guild.created_at)
        embed.set_author(name=guild.name, icon_url=guild.icon.url)
        embed.add_field(name='Owner', value=guild.owner)
        embed.add_field(name='Region', value=str(guild.region).capitalize())
        embed.add_field(name='Channel Categories', value=f'{len(guild.categories):,}')
        embed.add_field(name='Text Channels', value=f'{len(guild.text_channels):,}')
        embed.add_field(name='Voice Channels', value=f'{len(guild.voice_channels):,}')
        embed.add_field(name='Members', value=f'{guild.member_count:,}')
        embed.add_field(name='Roles', value=f'{len(guild.roles):,}')
        embed.set_footer(text='Server created')
        embed.set_thumbnail(url=guild.icon.with_size(4096).url)
        await ctx.reply(embed=embed)


def setup(client: Pidroid) -> None:
    client.add_cog(InfoCommands(client))
