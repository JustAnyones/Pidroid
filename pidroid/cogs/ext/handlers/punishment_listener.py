import logging

from discord.member import Member
from discord.user import User
from discord.embeds import Embed
from discord.ext import commands # type: ignore
from typing import Optional, Union

from pidroid.client import Pidroid
from pidroid.cogs.models.case import Ban, Warning, Jail, Kick, Timeout

logger = logging.getLogger("Pidroid")

class PunishmentListener(commands.Cog): # type: ignore
    """This class implements a cog for listening to custom Pidroid punishments."""

    def __init__(self, client: Pidroid):
        self.client = client

        # Register some listeners to custom Pidroid punishment events
        self.client.api.add_listener("on_ban_issued", self.on_ban_issued)
        self.client.api.add_listener("on_ban_revoked", self.on_ban_revoked)
        self.client.api.add_listener("on_ban_expired", self.on_ban_expired)
        self.client.api.add_listener("on_jail_issued", self.on_jail_issued)
        self.client.api.add_listener("on_jail_revoked", self.on_jail_revoked)
        self.client.api.add_listener("on_kick_issued", self.on_kick_issued)
        self.client.api.add_listener("on_timeout_issued", self.on_timeout_issued)
        self.client.api.add_listener("on_timeout_revoked", self.on_timeout_revoked)
        self.client.api.add_listener("on_timeout_expired", self.on_timeout_expired)
        self.client.api.add_listener("on_warning_issued", self.on_warning_issued)

    async def _message_user(self, user: Union[Member, User], embed: Embed):
        try:
            await user.send(embed=embed)
        except Exception: # nosec
            pass

    # Listeners
    async def on_ban_issued(self, ban: Ban):
        await self._message_user(ban.user, ban.private_message_issue_embed)

    async def on_ban_revoked(self, ban: Ban):
        await self._message_user(ban.user, ban.private_message_revoke_embed)

    async def on_ban_expired(self, ban: Ban):
        pass

    async def on_kick_issued(self, kick: Kick):
        await self._message_user(kick.user, kick.private_message_issue_embed)

    async def on_jail_issued(self, jail: Jail):
        await self._message_user(jail.user, jail.private_message_issue_embed)

    async def on_jail_revoked(self, jail: Jail):
        await self._message_user(jail.user, jail.private_message_revoke_embed)

    async def on_timeout_issued(self, timeout: Timeout):
        await self._message_user(timeout.user, timeout.private_message_issue_embed)

    async def on_timeout_revoked(self, timeout: Timeout):
        await self._message_user(timeout.user, timeout.private_message_revoke_embed)

    async def on_timeout_expired(self, timeout: Timeout):
        pass

    async def on_warning_issued(self, warning: Warning):
        await self._message_user(warning.user, warning.private_message_issue_embed)

async def setup(client: Pidroid) -> None:
    await client.add_cog(PunishmentListener(client))
