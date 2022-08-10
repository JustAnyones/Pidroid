import re

from discord.ext import commands # type: ignore
from discord.ext.commands.context import Context # type: ignore
from discord.ext.commands.errors import BadArgument # type: ignore
from discord.utils import escape_markdown
from mcrcon import MCRcon # type: ignore # TODO: reimplement locally
from typing import Dict

from pidroid.client import Pidroid

class MinecraftCommands(commands.Cog): # type: ignore
    """This class implements a cog for interacting with Minecraft servers over RCON using commands."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client

    @commands.command( # type: ignore
        brief='Sends minecraft command to specified server using rcon protocol.',
        usage='<server> <command>',
        permissions=["Minecraft server owner"]
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    async def rcon(self, ctx: Context, server_type: str = 'none', *, command: str = 'list'):
        async with ctx.typing():
            server_type = server_type.lower()
            try:
                servers: Dict[str, Dict[str, str]] = self.client.config['authentication']['minecraft rcon']
            except KeyError:
                raise BadArgument('Minecraft RCON configuration not found!')

            server_names = servers.keys()

            if len(server_names) == 0:
                raise BadArgument('No servers found!')

            if server_type not in server_names:
                raise BadArgument((
                    f'Specified server could not found.\nAvailable servers are ``{"``, ``".join(servers)}``.'
                ))

            s = servers[server_type]
            if ctx.author.id not in s['managers']:
                raise BadArgument('You are not an authorized manager for the specified server!')

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
                raise BadArgument('Connection has been refused by the server. Perhaps it is offline?')


async def setup(client: Pidroid) -> None:
    await client.add_cog(MinecraftCommands(client))
