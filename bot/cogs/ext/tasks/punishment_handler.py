import discord
import traceback
import sys

from discord.ext import tasks, commands
from discord.guild import Guild
from discord.utils import get
from typing import Union

from client import Pidroid
from cogs.utils.getters import get_user, get_role
from cogs.utils.time import utcnow

class PunishmentHandlerTask(commands.Cog):
    """This class implements a cog for automatic punishment revocation and reassignment."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client
        self.api = self.client.api
        self.check_punishments.start()

    def cog_unload(self) -> None:
        """Ensure that tasks are cancelled on cog unload."""
        self.check_punishments.stop()

    async def handle_ban(self, guild: Guild, user: Union[discord.Member, discord.User]) -> None:
        """Handles automatic unban in relation to the guild."""
        await self.api.revoke_punishment("ban", guild.id, user.id)
        guild_bans = await guild.bans()
        if get(guild_bans, user=user):
            await guild.unban(user, reason='Ban expired')

    async def handle_unmute(self, guild: Guild, member_id: int) -> None:
        """Handles automatic unmute in relation to the guild."""
        await self.api.revoke_punishment("mute", guild.id, member_id)
        mute_role = self.client.get_guild_configuration(guild.id).mute_role
        if mute_role is None:
            return
        member = guild.get_member(member_id)
        if member is None:
            return

        if get(member.roles, id=mute_role) is None:
            return
        await member.remove_roles(
            get(guild.roles, id=mute_role),
            reason="Mute expired"
        )

    @tasks.loop(seconds=5)
    async def check_punishments(self) -> None:
        """Periodically checks for expired punishments to remove."""
        try:
            current_time = int(utcnow().timestamp())
            for guild in self.client.guilds:
                punishments = await self.api.get_active_guild_punishments(guild.id)
                for p in punishments:
                    if current_time >= p['date_expires']:
                        user = await get_user(self.client, p["user"]["id"])

                        if p['type'] == 'ban':
                            await self.handle_ban(guild, user)
                        elif p['type'] == 'mute':
                            await self.handle_unmute(guild, user.id)

        except Exception as e:
            self.client.logger.exception("An exception was encountered while trying to check punishments")
            traceback.print_exception(type(e), e, e.__traceback__, file=sys.stderr)

    @check_punishments.before_loop
    async def before_check_punishments(self) -> None:
        """Runs before check_punishment task to ensure that the task is allowed to run."""
        await self.client.wait_guild_config_cache_ready()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Handles role-based punishment revocation for new members."""
        await self.client.wait_guild_config_cache_ready()
        member_guild_id = member.guild.id
        c = self.client.get_guild_configuration(member_guild_id)
        if c is None:
            return

        jail_role = c.jail_role
        if get_role(member.guild, jail_role) is not None:
            if not await self.api.has_punishment_expired('jail', member_guild_id, member.id):
                await member.add_roles(get(member.guild.roles, id=jail_role), reason="Jailed automatically as punishment evasion was detected.")

        mute_role = c.mute_role
        if get_role(member.guild, mute_role) is not None:
            if not await self.api.has_punishment_expired('mute', member_guild_id, member.id):
                await member.add_roles(get(member.guild.roles, id=mute_role), reason="Muted automatically as punishment evasion was detected.")

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: Union[discord.Member, discord.User]) -> None:
        """Removes ban records from the database for an unbanned user."""
        await self.client.wait_until_ready()
        await self.api.revoke_punishment('ban', guild.id, user.id)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        """Handles jail and mute role removal."""
        await self.client.wait_guild_config_cache_ready()

        guild_id = before.guild.id
        changed_roles = list(set(before.roles) - set(after.roles)) or None
        if changed_roles is None:
            return

        c = self.client.get_guild_configuration(guild_id)
        if c is None:
            return

        if changed_roles[0].id == c.jail_role:
            if await self.api.is_currently_jailed(guild_id, after.id):
                await self.api.revoke_punishment('jail', guild_id, after.id)
                return

        if changed_roles[0].id == c.mute_role:
            if await self.api.is_currently_muted(guild_id, after.id):
                await self.api.revoke_punishment('mute', guild_id, after.id)
                return


def setup(client: Pidroid) -> None:
    client.add_cog(PunishmentHandlerTask(client))
