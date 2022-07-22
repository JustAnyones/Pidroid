import discord
import traceback
import sys

from contextlib import suppress
from discord.ext import tasks, commands # type: ignore
from typing import Union

from client import Pidroid
from cogs.utils.getters import get_role

class PunishmentHandlerTask(commands.Cog): # type: ignore
    """This class implements a cog for automatic punishment revocation and reassignment."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client
        self.check_punishments.start()

    def cog_unload(self) -> None:
        """Ensure that tasks are cancelled on cog unload."""
        self.check_punishments.stop()

    @tasks.loop(seconds=5)
    async def check_punishments(self) -> None:
        """Periodically checks for expired punishments to remove."""
        try:
            for guild in self.client.guilds:
                punishments = await self.client.api.fetch_active_expiring_guild_punishments(guild.id)
                for punishment in punishments:

                    # Immediately expire the punishment as far as DB is concerned
                    await self.client.api.revoke_cases_by_type(punishment.type, guild.id, punishment.user_id)

                    # If user is not able to be resolved, just skip everything
                    if punishment.user is None:
                        continue
                    
                    # Remove ban entry from Discord
                    if punishment.type == "ban":
                        with suppress(Exception):
                            await guild.unban(punishment.user, reason=f"Ban expired | Case #{punishment.case_id}") # type: ignore

                    # Remove mute role from user
                    elif punishment.type == "mute":
                        config = self.client.get_guild_configuration(guild.id)
                        assert config is not None

                        if config.mute_role is None:
                            continue

                        member = guild.get_member(punishment.user_id)
                        if member is None:
                            continue

                        mute_role = get_role(guild, config.mute_role)
                        if mute_role is None:
                            continue
                        await member.remove_roles(mute_role, reason=f"Mute expired | Case #{punishment.case_id}") # type: ignore

        except Exception as e:
            self.client.logger.exception("An exception was encountered while trying to check punishments")
            traceback.print_exception(type(e), e, e.__traceback__, file=sys.stderr)

    @check_punishments.before_loop
    async def before_check_punishments(self) -> None:
        """Runs before check_punishment task to ensure that the task is allowed to run."""
        await self.client.wait_guild_config_cache_ready()

    @commands.Cog.listener() # type: ignore
    async def on_member_join(self, member: discord.Member) -> None:
        """Handles role-based punishment revocation for new members."""
        await self.client.wait_guild_config_cache_ready()

        c = self.client.get_guild_configuration(member.guild.id)
        assert c is not None

        jail_role = get_role(member.guild, c.jail_role)
        if jail_role is not None:
            if await self.client.api.is_currently_jailed(member.guild.id, member.id):
                await member.add_roles(jail_role, reason="Jailed automatically as punishment evasion was detected.") # type: ignore

        mute_role = get_role(member.guild, c.mute_role)
        if mute_role is not None:
            if await self.client.api.is_currently_muted(member.guild.id, member.id):
                await member.add_roles(mute_role, reason="Muted automatically as punishment evasion was detected.") # type: ignore

    @commands.Cog.listener() # type: ignore
    async def on_member_unban(self, guild: discord.Guild, user: Union[discord.Member, discord.User]) -> None:
        """Removes ban records from the database for an unbanned user."""
        await self.client.wait_until_ready()
        await self.client.api.revoke_cases_by_type('ban', guild.id, user.id)

    @commands.Cog.listener() # type: ignore
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        """Handles jail and mute role removal."""
        await self.client.wait_guild_config_cache_ready()

        guild_id = before.guild.id
        changed_roles = list(set(before.roles) - set(after.roles)) or None
        if changed_roles is None:
            return

        c = self.client.get_guild_configuration(guild_id)
        assert c is not None

        if changed_roles[0].id == c.jail_role:
            if await self.client.api.is_currently_jailed(guild_id, after.id):
                return await self.client.api.revoke_cases_by_type('jail', guild_id, after.id)

        if changed_roles[0].id == c.mute_role:
            if await self.client.api.is_currently_muted(guild_id, after.id):
                return await self.client.api.revoke_cases_by_type('mute', guild_id, after.id)


async def setup(client: Pidroid) -> None:
    await client.add_cog(PunishmentHandlerTask(client))
