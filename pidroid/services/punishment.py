import discord
import logging

from contextlib import suppress
from discord.ext import tasks, commands
from typing import override

from pidroid.client import Pidroid
from pidroid.modules.moderation.models.types import PunishmentType2
from pidroid.utils.aliases import DiscordUser

logger = logging.getLogger("Pidroid")

class PunishmentService(commands.Cog):
    """This class implements a cog for automatic punishment revocation and reassignment."""

    def __init__(self, client: Pidroid) -> None:
        super().__init__()
        self.client: Pidroid = client
        _ = self.remove_expired_bans.start()

    @override
    async def cog_unload(self):
        """Ensure that tasks are cancelled on cog unload."""
        self.remove_expired_bans.stop()

    @tasks.loop(seconds=5)
    async def remove_expired_bans(self) -> None:
        """Periodically checks for expired punishments to remove."""
        try:
            for guild in self.client.guilds:
                bans = await self.client.api.fetch_active_guild_bans(guild.id)
                for ban in bans:
                    assert ban.type == PunishmentType2.BAN
                    # Immediately expire the punishment as far as DB is concerned
                    await ban.expire()
                    # If user is not able to be resolved, just skip everything
                    banned_user = await self.client.get_or_fetch_user(ban.user_id)
                    if banned_user is None:
                        continue
                    # Remove ban entry from Discord
                    with suppress(Exception):
                        await guild.unban(banned_user, reason=f"Ban expired | Case #{ban.case_id}")
        except Exception:
            logger.exception("An exception was encountered while trying remove expired bans")

    @remove_expired_bans.before_loop
    async def before_remove_expired_bans(self) -> None:
        """Runs before remove_expired_bans task to ensure that the task is allowed to run."""
        await self.client.wait_until_guild_configurations_loaded()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Handles role-based punishment revocation for new members."""
        await self.client.wait_until_guild_configurations_loaded()

        c = await self.client.fetch_guild_configuration(member.guild.id)

        if c.jail_role_id is None:
            return

        jail_role = member.guild.get_role(c.jail_role_id)
        if jail_role is not None:
            if await self.client.api.is_currently_jailed(member.guild.id, member.id):
                await member.add_roles(
                    jail_role,
                    reason="Jailed automatically as punishment evasion was detected."
                )

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: DiscordUser) -> None:
        """Removes ban records from the database for an unbanned user."""
        await self.client.wait_until_ready()
        await self.client.api.expire_cases_by_type(PunishmentType2.BAN, guild.id, user.id)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        """Handles jail role removal."""
        await self.client.wait_until_guild_configurations_loaded()

        guild_id = before.guild.id
        changed_roles = list(set(before.roles) - set(after.roles)) or None
        if changed_roles is None:
            return

        c = await self.client.fetch_guild_configuration(guild_id)

        if changed_roles[0].id == c.jail_role_id:
            if await self.client.api.is_currently_jailed(guild_id, after.id):
                return await self.client.api.expire_cases_by_type(PunishmentType2.JAIL, guild_id, after.id)

async def setup(client: Pidroid) -> None:
    await client.add_cog(PunishmentService(client))
