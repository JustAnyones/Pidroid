from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import Response
from discord.channel import TextChannel
from discord.ext import commands
from multidict import MultiDictProxy

from client import Pidroid
from cogs.utils.checks import is_client_pidroid


class HTTPServerTask(commands.Cog):
    """This class implements a cog for handling an asynchronous HTTP server.

    This only does internal IPC communications between the public facing PHP API and discord."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client
        self.server_task = self.client.loop.create_task(self.web_server())

    def cog_unload(self) -> None:
        """Ensure that server is closed on cog unload."""
        self.client.logger.info("Stopping HTTP server, task and cog")
        if self.site:
            self.client.loop.create_task(self.site.stop())
        self.server_task.cancel()
        self.client.logger.info("HTTP server stopped and cog unloaded")

    async def handle_unlock_final_type(self, query: MultiDictProxy) -> Response:
        """Handles the final unlock action."""
        # If hunt is already complete
        if self.client.scavenger_hunt["complete"]:
            return web.json_response({"success": False, "code": 3, "details": "Scavenger hunt is already completed!"})
        self.client.scavenger_hunt["complete"] = True

        if self.client.http_server_testing:
            return web.json_response({"success": True, "code": 4, "details": "Your unlock_final operation has been understood, however the server is currently in testing mode"})

        # Grab the currently hidden channel
        channel: TextChannel = await self.client.fetch_channel(796115960577654864)

        # If Lobby's API manages to grab the city author name
        mayor_name = query.get("mayor", None)
        if mayor_name:
            # Log it internally
            self.client.logger.critical(f"{mayor_name} finished the scavenger hunt!")

        # Send a message
        await channel.send(self.client.scavenger_hunt["full_message"])

        # Unlock channel for everyone else to see
        await channel.set_permissions(channel.guild.default_role, read_messages=True, reason="Scavenger hunt solved!")

        return web.json_response({"success": True, "code": 4, "details": "Operation has been successful"})

    async def handle_status_type(self) -> Response:
        """Handles the status request action."""
        return web.json_response({"success": True, "code": 5, "hunt_complete": self.client.scavenger_hunt["complete"]})

    async def web_server(self) -> None:
        """Implements a simple HTTP server using aiohttp."""
        await self.client.wait_until_ready()
        # Lazy approach to ensure the scavenger data is loaded by fetching it before caching configs
        await self.client.wait_guild_config_cache_ready()
        if not is_client_pidroid(self.client):
            return

        async def handler(request: Request) -> Response:
            """Handles the GET request and returns response."""
            query: MultiDictProxy = request.url.query
            request_type = query.get("type", None)

            if request_type is None:
                return web.json_response({"success": False, "code": 1, "details": "Type parameter is not specified"})

            if request_type == "unlock_final":
                return await self.handle_unlock_final_type(query)

            if request_type == "status":
                return await self.handle_status_type()

            return web.json_response({"success": False, "code": 2, "details": "Wrong type parameter specified"})

        # What do you mean this is overkill? I can't hear you over my huge brain expanding by my brilliance
        # https://www.youtube.com/watch?v=weUDuqA6dF4&t=10s
        app = web.Application()
        app.router.add_get('/', handler)
        runner = web.AppRunner(app)
        await runner.setup()
        self.site = web.TCPSite(runner, '127.0.0.1', 42069) # Czechmate, hackers
        # TODO: ensure port 42069 is not open to the world
        await self.site.start()

def setup(client: Pidroid) -> None:
    client.add_cog(HTTPServerTask(client))
