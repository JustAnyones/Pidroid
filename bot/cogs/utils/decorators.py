from discord.ext import commands
from discord.errors import InvalidArgument
from discord.ext.commands.context import Context

from constants import BOT_COMMANDS_CHANNEL, EMERGENCY_SHUTDOWN
from cogs.models.exceptions import ClientIsNotPidroid, InvalidChannel, NotInTheoTownGuild, MissingUserPermissions
from cogs.utils.checks import (
    is_bot_commands, is_cheese_consumer, is_client_development, is_theotown_developer, is_theotown_guild,
    check_permissions, guild_has_configuration, check_junior_moderator_permissions,
    check_normal_moderator_permissions, check_senior_moderator_permissions, can_purge
)

# noinspection PyPep8Naming
class command_checks:
    """This class contains custom command check decorators."""

    @staticmethod
    def is_theotown_guild():
        """Checks whether the command is invoked inside TheoTown guild."""
        async def predicate(ctx: Context):
            if not is_theotown_guild(ctx.guild):
                raise NotInTheoTownGuild
            return True
        return commands.check(predicate)

    @staticmethod
    def is_bot_commands():
        """Checks whether the command is invoked in a channel for bot commands."""
        async def predicate(ctx: Context):
            if not is_bot_commands(ctx.channel):
                raise InvalidChannel(f'The command can only be used inside <#{BOT_COMMANDS_CHANNEL}> channel')
            return True
        return commands.check(predicate)

    @staticmethod
    def is_theotown_developer():
        """Checks whether the command is invoked by a TheoTown developer."""
        async def predicate(ctx: Context):
            if not is_theotown_developer(ctx.author):
                raise MissingUserPermissions('You are not a TheoTown developer!')
            return True
        return commands.check(predicate)

    @staticmethod
    def guild_configuration_exists():
        """Checks whether the command is invoked in a guild with Pidroid configuration."""
        async def predicate(ctx: Context):
            if not guild_has_configuration(ctx.bot, ctx.guild):
                raise InvalidArgument('Server does not have a moderation system set up!')
            return True
        return commands.check(predicate)

    @staticmethod
    def is_junior_moderator(**perms):
        """Checks whether the command is invoked by a junior moderator."""
        async def predicate(ctx: Context):
            return check_junior_moderator_permissions(ctx, **perms)
        return commands.check(predicate)

    @staticmethod
    def is_moderator(**perms):
        """Checks whether the command is invoked by a normal moderator."""
        async def predicate(ctx: Context):
            return check_normal_moderator_permissions(ctx, **perms)
        return commands.check(predicate)

    @staticmethod
    def is_senior_moderator(**perms):
        """Checks whether the command is invoked by a senior moderator."""
        async def predicate(ctx: Context):
            return check_senior_moderator_permissions(ctx, **perms)
        return commands.check(predicate)

    @staticmethod
    def can_purge():
        """Checks whether the command is invoked by a member which can purge."""
        async def predicate(ctx: Context):
            if is_theotown_guild(ctx.guild):
                if not can_purge(ctx.author):
                    raise MissingUserPermissions('You need to be at least a moderator or event organiser to run this command!')
                return True
            return check_permissions(ctx, manage_messages=True)
        return commands.check(predicate)

    @staticmethod
    def is_cheese_consumer():
        """Checks whether the command is invoked by an authorized user."""
        async def predicate(ctx: Context):
            if not is_cheese_consumer(ctx.author):
                raise MissingUserPermissions(
                    f'Sorry {ctx.author.display_name}, I can\'t run that command. Come back when you\'re a little, mmmmm, richer!'
                )
            return True
        return commands.check(predicate)

    @staticmethod
    def can_shutdown_bot():
        """Checks whether the command is invoked by an authorized user to shutdown the bot."""
        async def predicate(ctx: Context):
            if ctx.author.id not in EMERGENCY_SHUTDOWN:
                raise MissingUserPermissions(
                    "You are not authorized to perform an emergency shutdown!"
                )
            return True
        return commands.check(predicate)

    @staticmethod
    def client_is_pidroid():
        """Checks whether the command invocation is handled by the original Pidroid client user."""
        async def predicate(ctx: Context):
            if is_client_development(ctx.bot):
                raise ClientIsNotPidroid
            return True
        return commands.check(predicate)


def setup(client):
    pass

def teardown(client):
    pass
