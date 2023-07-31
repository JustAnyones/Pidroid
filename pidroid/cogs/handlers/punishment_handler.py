import discord

from contextlib import suppress
from discord.ext import tasks, commands # type: ignore
from typing import Union

from pidroid.client import Pidroid
from pidroid.models.punishments import PunishmentType, Ban, Warning, Jail, Kick, Timeout
from pidroid.utils import try_message_user

class PunishmentHandlerTask(commands.Cog): # type: ignore
    """This class implements a cog for automatic punishment revocation and reassignment."""

    def __init__(self, client: Pidroid) -> None:
        self.client = client
        self.remove_expired_bans.start()

    def cog_unload(self):
        """Ensure that tasks are cancelled on cog unload."""
        self.remove_expired_bans.stop()

    @tasks.loop(seconds=5)
    async def remove_expired_bans(self) -> None:
        """Periodically checks for expired punishments to remove."""
        try:
            for guild in self.client.guilds:
                bans = await self.client.api.fetch_active_guild_bans(guild.id)
                for ban in bans:
                    assert ban.type == PunishmentType.ban
                    # Immediately expire the punishment as far as DB is concerned
                    await ban.expire()
                    # If user is not able to be resolved, just skip everything
                    if ban.user is None:
                        continue
                    # Remove ban entry from Discord
                    with suppress(Exception):
                        await guild.unban(ban.user, reason=f"Ban expired | Case #{ban.case_id}")
        except Exception:
            self.client.logger.exception("An exception was encountered while trying remove expired bans")

    @remove_expired_bans.before_loop
    async def before_remove_expired_bans(self) -> None:
        """Runs before remove_expired_bans task to ensure that the task is allowed to run."""
        await self.client.wait_until_guild_configurations_loaded()

    @commands.Cog.listener() # type: ignore
    async def on_member_join(self, member: discord.Member) -> None:
        """Handles role-based punishment revocation for new members."""
        await self.client.wait_until_guild_configurations_loaded()

        c = await self.client.fetch_guild_configuration(member.guild.id)

        if c.jail_role_id is None:
            return

        jail_role = await self.client.get_or_fetch_role(member.guild, c.jail_role_id)
        if jail_role is not None:
            if await self.client.api.is_currently_jailed(member.guild.id, member.id):
                await member.add_roles(
                    jail_role,
                    reason="Jailed automatically as punishment evasion was detected."
                ) # type: ignore

    @commands.Cog.listener() # type: ignore
    async def on_member_unban(self, guild: discord.Guild, user: Union[discord.Member, discord.User]) -> None:
        """Removes ban records from the database for an unbanned user."""
        await self.client.wait_until_ready()
        await self.client.api.expire_cases_by_type(PunishmentType.ban, guild.id, user.id)

    @commands.Cog.listener() # type: ignore
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
                return await self.client.api.expire_cases_by_type(PunishmentType.jail, guild_id, after.id)

    """Listen to Pidroid punishment creations and send notifications."""

    # Listeners
    @commands.Cog.listener()
    async def on_pidroid_ban_issue(self, ban: Ban):
        pass

    @commands.Cog.listener()
    async def on_pidroid_ban_revoke(self, ban: Ban):
        await try_message_user(ban.user, ban.private_message_revoke_embed)

    @commands.Cog.listener()
    async def on_pidroid_ban_expire(self, ban: Ban):
        # TODO: implement
        pass

    @commands.Cog.listener()
    async def on_pidroid_kick_issue(self, kick: Kick):
        pass

    @commands.Cog.listener()
    async def on_pidroid_jail_issue(self, jail: Jail):
        await try_message_user(jail.user, jail.private_message_issue_embed)

    @commands.Cog.listener()
    async def on_pidroid_jail_revoke(self, jail: Jail):
        await try_message_user(jail.user, jail.private_message_revoke_embed)

    @commands.Cog.listener()
    async def on_pidroid_timeout_issue(self, timeout: Timeout):
        await try_message_user(timeout.user, timeout.private_message_issue_embed)

    @commands.Cog.listener()
    async def on_pidroid_timeout_revoke(self, timeout: Timeout):
        await try_message_user(timeout.user, timeout.private_message_revoke_embed)

    @commands.Cog.listener()
    async def on_pidroid_timeout_expire(self, timeout: Timeout):
        # TODO: implement
        pass

    @commands.Cog.listener()
    async def on_pidroid_warning_issue(self, warning: Warning):
        await try_message_user(warning.user, warning.private_message_issue_embed)


async def setup(client: Pidroid) -> None:
    await client.add_cog(PunishmentHandlerTask(client))
