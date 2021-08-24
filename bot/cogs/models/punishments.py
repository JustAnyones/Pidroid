import discord

from datetime import timedelta
from discord.ext.commands.context import Context
from discord.ext.commands.errors import BadArgument
from discord.errors import Forbidden
from discord.guild import Guild
from discord.role import Role
from typing import Union

from cogs.utils.api import API
from cogs.utils.embeds import success
from cogs.utils.time import timedelta_to_datetime, utcnow

class Punishment:

    def __init__(self, ctx: Context):
        self.ctx = ctx
        self.api: API = ctx.bot.api

        self.guild: Guild = ctx.guild
        self.user: Union[discord.Member, discord.User] = None
        self.moderator: Union[discord.Member, discord.User] = ctx.author
        self.date_issued = int(utcnow().timestamp())

        self.silent = False

        self.case_id = None

        self._reason = None
        self._length = None

    @property
    def reason(self) -> str:
        return self._reason

    @reason.setter
    def reason(self, reason: str):
        if reason is None:
            return

        if len(reason) > 512:
            raise BadArgument("Your reason is too long. Please make sure it's below or equal to 512 characters!")
        self._reason = reason

    @property
    def length(self) -> int:
        if self._length is None:
            return -1
        return self._length

    # TODO: add support for various length parameters
    @length.setter
    def length(self, length: Union[int, timedelta]):
        if isinstance(length, timedelta):
            length = timedelta_to_datetime(length).timestamp()
        self._length = int(length)

    @property
    def user_username(self) -> str:
        """Returns the full username of a user."""
        return str(self.user)

    @property
    def moderator_username(self) -> str:
        """Returns the full username of a moderator."""
        return str(self.moderator)

    async def _issue(self, punishment_type: str):
        """Issues the specified punishment."""
        self.case_id = await self.api.create_punishment(
            punishment_type, self.guild.id,
            self.user.id, self.user_username,
            self.moderator.id, self.moderator_username,
            self.date_issued, self.reason, self.length
        )

    async def _revoke(self, punishment_type: str) -> None:
        """Revokes all punishments of specified type for the user."""
        self.case_id = await self.api.revoke_punishment(punishment_type, self.guild.id, self.user.id)

    async def _notify_user(self, message: str):
        """Sends a message to the punished user notifying of the punishment."""
        try:
            await self.user.send(message)
        except Forbidden:
            pass

    async def _notify_chat(self, message: str, image: discord.File = None):
        """Sends a message to the channel the command was ran from notifying about the punishment."""
        try:
            if not self.silent:
                if self.case_id is not None:
                    embed = success(
                        title=f"Case #{self.case_id}",
                        description=message
                    )
                    if image is not None:
                        embed.set_image(url="attachment://picture.png")
                else:
                    embed = success(description=message)
                await self.ctx.send(embed=embed, file=image)
        except Forbidden:
            pass


class Ban(Punishment):

    def __init__(self, ctx: Context, user: Union[discord.Member, discord.User], reason: str = None):
        super().__init__(ctx)
        self.user = user
        self.reason = reason

    async def issue(self):
        """Bans the user."""
        await self._revoke('jail')
        await self._revoke('mute')
        await self._issue('ban')

        if self.reason is None:
            await self._notify_chat(f"{self.user_username} was banned!")
            await self._notify_user(f"You have been banned from {self.guild.name} server!")
        else:
            await self._notify_chat(f'{self.user_username} was banned for the following reason: {self.reason}')
            await self._notify_user(f"You have been banned from {self.guild.name} server for the following reason: {self.reason}")

        await self.guild.ban(user=self.user, reason=self.reason)


class Kick(Punishment):

    def __init__(self, ctx: Context, user: discord.Member, reason: str = None):
        super().__init__(ctx)
        self.user = user
        self.reason = reason

    async def issue(self):
        """Kicks the member."""
        await self._revoke('jail')
        await self._revoke('mute')
        await self._issue('kick')

        if self.reason is None:
            await self._notify_chat(f"{self.user_username} was kicked!")
            await self._notify_user(f"You have been kicked from {self.guild.name} server!")
        else:
            await self._notify_chat(f'{self.user_username} was kicked for the following reason: {self.reason}')
            await self._notify_user(f"You have been kicked from {self.guild.name} server for the following reason: {self.reason}")

        await self.user.kick(reason=self.reason)


class Jail(Punishment):

    def __init__(self, ctx: Context, user: discord.Member, role: Role, reason: str = None):
        super().__init__(ctx)
        self.user = user
        self.role = role
        self.reason = reason

    async def issue(self):
        """Jails the member."""
        await self._issue("jail")
        await self.user.add_roles(
            discord.utils.get(self.guild.roles, id=self.role.id),
            reason=f"Jailed by {self.moderator_username}"
        )

        if self.reason is None:
            await self._notify_chat(f"{self.user_username} was jailed!")
            await self._notify_user(f"You have been jailed in {self.guild.name} server!")
        else:
            await self._notify_chat(f"{self.user_username} was jailed for the following reason: {self.reason}")
            await self._notify_user(f"You have been jailed in {self.guild.name} server for the following reason: {self.reason}")

    async def revoke(self):
        """Unjails the member."""
        await self._revoke("jail")
        await self.user.remove_roles(
            discord.utils.get(self.guild.roles, id=self.role.id),
            reason=f"Unjailed by {self.moderator_username}"
        )

        await self._notify_chat(f"{self.user_username} was unjailed!")
        await self._notify_user(f"You have been unjailed in {self.guild.name} server!")


class Kidnap(Punishment):

    def __init__(self, ctx: Context, user: discord.Member, role: Role, reason: str = None):
        super().__init__(ctx)
        self.user = user
        self.role = role
        self.reason = reason

    async def issue(self):
        """Kidnaps the member.\n
        Alias for jail."""
        await self._issue("jail")
        await self.user.add_roles(
            discord.utils.get(self.guild.roles, id=self.role.id),
            reason=f"Jailed by {self.moderator_username}"
        )

        if self.reason is None:
            await self._notify_chat(f"{self.user_username} was kidnapped!", image=discord.File('./resources/bus.png'))
            await self._notify_user(f"You have been kidnapped in {self.guild.name} server!")
        else:
            await self._notify_chat(f"{self.user_username} was kidnapped for the following reason: {self.reason}", image=discord.File('./resources/bus.png'))
            await self._notify_user(f"You have been kidnapped in {self.guild.name} server for the following reason: {self.reason}")

    async def revoke(self):
        """Unjails the member."""
        await self._revoke("jail")
        await self.user.remove_roles(
            discord.utils.get(self.guild.roles, id=self.role.id),
            reason=f"Unjailed by {self.moderator_username}"
        )

        await self._notify_chat(f"{self.user_username} was unjailed!")
        await self._notify_user(f"You have been unjailed in {self.guild.name} server!")


class Mute(Punishment):

    def __init__(self, ctx: Context, user: discord.Member, role: Role, reason: str = None):
        """Initializes mute punishment instance.\n
        Reason can be optionally entered."""
        super().__init__(ctx)
        self.user = user
        self.role = role
        self.reason = reason

    async def issue(self):
        """Mutes the member."""
        await self._issue("mute")
        await self.user.add_roles(
            discord.utils.get(self.guild.roles, id=self.role.id),
            reason=f"Muted by {self.moderator_username}"
        )

        if self.reason is None:
            await self._notify_chat(f"{self.user_username} was muted!")
            await self._notify_user(f"You have been muted in {self.guild.name} server!")
        else:
            await self._notify_chat(f"{self.user_username} was muted for the following reason: {self.reason}")
            await self._notify_user(f"You have been muted in {self.guild.name} server for the following reason: {self.reason}")

    async def revoke(self):
        """Unmutes the member."""
        self._revoke("mute")
        await self.user.remove_roles(
            discord.utils.get(self.guild.roles, id=self.role.id),
            reason=f"Unmuted by {self.moderator_username}"
        )

        await self._notify_chat(f"{self.user_username} was unmuted!")
        await self._notify_user(f"You have been unmuted in {self.guild.name} server!")


class Warn(Punishment):

    def __init__(self, ctx: Context, user: discord.Member, warning: str):
        """Initializes warn punishment instance.\n
        Automatically sets length to 120 days."""
        super().__init__(ctx)
        self.user = user
        self.reason = warning
        self.length = timedelta(days=120)

    async def issue(self):
        """Issues a warning to the member."""
        await self._issue('warning')
        await self._notify_chat(f"{self.user_username} has been warned: {self.reason}")
        await self._notify_user(f"You have been warned in {self.guild.name} server: {self.reason}")


def setup(client):
    pass

def teardown(client):
    pass
