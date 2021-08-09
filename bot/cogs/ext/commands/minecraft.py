import re

from discord.ext import commands
from discord.ext.commands.context import Context
from discord.utils import escape_markdown
from mcrcon import MCRcon

from client import Pidroid
from cogs.utils.embeds import error

class MinecraftCommands(commands.Cog):
    """This class implements a cog for interacting with Minecraft servers over RCON using commands."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client

    @commands.command(
        brief='Sends minecraft command to specified server using rcon protocol.',
        usage='<server> <command>',
        permissions=["Minecraft server owner"]
    )
    @commands.bot_has_permissions(send_messages=True)
    async def rcon(self, ctx: Context, server_type: str = 'none', *, command: str = 'list'):
        async with ctx.typing():
            server_type = server_type.lower()
            try:
                servers = self.client.config['authentication']['minecraft rcon']
            except KeyError:
                await ctx.reply(embed=error('Minecraft RCON configuration not found!'))
                return

            server_names = servers.keys()

            if len(server_names) == 0:
                await ctx.reply(embed=error('No servers found!'))
                return

            if server_type not in server_names:
                await ctx.reply(embed=error(
                    f'Specified server could not found.\nAvailable servers are ``{"``, ``".join(servers)}``.'
                ))
                return

            s = servers[server_type]
            if ctx.author.id not in s['managers']:
                await ctx.reply(embed=error('You are not an authorized manager for the specified server!'))
                return

            address = s['address'].split(':')
            port = 25575
            if len(address) > 1:
                port = int(address[1])
            rcon = MCRcon(address[0], s['password'], port=port)

            try:
                rcon.connect()
                response = rcon.command(command)
                if len(response) == 0:
                    response = 'Command issued, RCON protocol did not return any information back.'
                response = re.sub(r'§.', '', response)
                await ctx.reply(escape_markdown(response))
                rcon.disconnect()
            except ConnectionRefusedError:
                await ctx.reply(embed=error('Connection has been refused by the server. Perhaps it is offline?'))


def setup(client: Pidroid) -> None:
    client.add_cog(MinecraftCommands(client))
