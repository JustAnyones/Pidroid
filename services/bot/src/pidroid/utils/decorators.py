from discord import Member
from discord.ext import commands
from discord.ext.commands import Context

from pidroid.client import Pidroid
from pidroid.constants import EMERGENCY_SHUTDOWN, CHEESE_EATERS
from pidroid.models.exceptions import ClientIsNotPidroid, NotInTheoTownGuild, MissingUserPermissions
from pidroid.utils.checks import (
    TheoTownChecks,
    is_client_pidroid, is_guild_theotown,
    check_can_modify_tags,
    assert_chat_moderator_permissions, assert_senior_moderator_permissions,
    assert_channel_permissions
)

class command_checks:
    """
    This class contains custom command check decorators.
    
    These checks are evaluated before command invocation to determine whether the command should be executed.
    For permission checks at runtime, use the `pidroid.utils.checks` module.
    """

    @staticmethod
    def is_theotown_developer():
        """Checks whether the command is invoked by a TheoTown developer."""
        async def predicate(ctx: Context[Pidroid]):
            if not TheoTownChecks.is_developer(ctx.author):
                raise MissingUserPermissions('You are not a TheoTown developer!')
            return True
        return commands.check(predicate)

    @staticmethod
    def is_cheese_consumer():
        """Checks whether the command is invoked by an authorized user."""
        async def predicate(ctx: Context[Pidroid]):
            if ctx.author.id not in CHEESE_EATERS:
                raise MissingUserPermissions(
                    f'Sorry {ctx.author.display_name}, I can\'t run that command. Come back when you\'re a little, mmmmm, richer!'
                )
            return True
        return commands.check(predicate)

    @staticmethod
    def can_shutdown_bot():
        """Checks whether the command is invoked by an authorized user to shutdown the bot."""
        async def predicate(ctx: Context[Pidroid]):
            if ctx.author.id not in EMERGENCY_SHUTDOWN:
                raise MissingUserPermissions(
                    "You are not authorized to perform an emergency shutdown!"
                )
            return True
        return commands.check(predicate)

    @staticmethod
    def client_is_pidroid():
        """Checks whether the command invocation is handled by the original Pidroid client user."""
        async def predicate(ctx: Context[Pidroid]):
            if not is_client_pidroid(ctx.bot):
                raise ClientIsNotPidroid
            return True
        return commands.check(predicate)



    """Guild only

    These decorators are only to be used inside the guild."""



    @staticmethod
    def is_theotown_guild():
        """Checks whether the command is invoked inside TheoTown guild."""
        async def predicate(ctx: Context[Pidroid]):
            assert ctx.guild is not None
            if not is_guild_theotown(ctx.guild):
                raise NotInTheoTownGuild
            return True
        return commands.check(predicate)

    @staticmethod
    def is_moderator(**perms: bool):
        """
        Checks whether the command is invoked by a moderator or a member with appropriate permissions.
        
        Evaluation is scoped to channel permissions if not in TheoTown guild.
        In TheoTown, a moderator is considered anyone with at least chat moderator role.
        """
        async def predicate(ctx: Context[Pidroid]):
            assert_chat_moderator_permissions(ctx, **perms)
            return True
        return commands.check(predicate)

    @staticmethod
    def is_senior_moderator(**perms: bool):
        """Checks whether the command is invoked by a senior moderator or a member with appropriate permissions."""
        async def predicate(ctx: Context[Pidroid]):
            assert_senior_moderator_permissions(ctx, **perms)
            return True
        return commands.check(predicate)

    @staticmethod
    def can_purge():
        """Checks whether the command is invoked by a member which can purge."""
        async def predicate(ctx: Context[Pidroid]):
            assert ctx.guild is not None
            assert isinstance(ctx.author, Member)
            if is_guild_theotown(ctx.guild):
                if not TheoTownChecks.is_normal_moderator(ctx.author):
                    raise MissingUserPermissions('You need to be at least a moderator to run this command!')
                return True
            assert_channel_permissions(ctx, manage_messages=True)
            return True
        return commands.check(predicate)

    @staticmethod
    def can_modify_tags():
        """Checks whether the command is invoked by a member who can manage tags."""
        async def predicate(ctx: Context[Pidroid]):
            return await check_can_modify_tags(ctx)
        return commands.check(predicate)
