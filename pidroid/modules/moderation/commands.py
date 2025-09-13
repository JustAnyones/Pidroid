import asyncio
import datetime
import discord

from dataclasses import dataclass
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import BadArgument, BadUnionArgument, Context, MissingRequiredArgument, UserNotFound

from pidroid.client import Pidroid
from pidroid.models.categories import ModerationCategory
from pidroid.modules.moderation.ui.modmenu.view import ModmenuView
from pidroid.services.error_handler import notify
from pidroid.utils.checks import is_guild_moderator
from pidroid.utils.time import utcnow

@dataclass
class UserSemaphore:
    semaphore: asyncio.Semaphore
    message_id: int | None
    message_url: str | None
    created: datetime.datetime

class ModerationCommandsCog(commands.Cog):
    """This class implements cog which contains commands for moderation."""

    def __init__(self, client: Pidroid):
        super().__init__()
        self.client: Pidroid = client
        self.user_semaphores: dict[int, dict[int, UserSemaphore]] = {}

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent) -> None:
        """Handles removal of semaphore from users if their modmenu message was deleted."""
        if payload.guild_id is None:
            return

        guild_semaphores = self.user_semaphores.get(payload.guild_id)
        if guild_semaphores is None:
            return

        for user_id in guild_semaphores.copy().keys():
            msg_id = guild_semaphores[user_id].message_id
            if msg_id is not None and msg_id == payload.message_id:
                await self.unlock_punishment_menu(payload.guild_id, user_id)
                return

    def _create_semaphore_if_not_exist(
        self,
        guild_id: int, user_id: int,
        message_id: int | None = None,
        message_url: str | None = None
    ) -> asyncio.Semaphore:
        if self.user_semaphores.get(guild_id) is None:
            self.user_semaphores[guild_id] = {}
        user = self.user_semaphores[guild_id].get(user_id)
        if user is None:
            self.user_semaphores[guild_id][user_id] = UserSemaphore(
                semaphore=asyncio.Semaphore(1),
                message_id=message_id,
                message_url=message_url,
                created=utcnow()
            )
        return self.user_semaphores[guild_id][user_id].semaphore

    async def lock_punishment_menu(
        self,
        guild_id: int, user_id : int,
        message_id: int | None = None,
        message_url: str | None = None
    ) -> None:
        sem = self._create_semaphore_if_not_exist(guild_id, user_id, message_id, message_url)
        _ = await sem.acquire()

    async def unlock_punishment_menu(self, guild_id: int, user_id: int) -> None:
        sem = self._create_semaphore_if_not_exist(guild_id, user_id)
        sem.release()
        # Save memory with this simple trick
        _ = self.user_semaphores[guild_id].pop(user_id)

    def get_user_semaphore(self, guild_id: int, user_id: int) -> UserSemaphore | None:
        guild = self.user_semaphores.get(guild_id)
        if guild is None:
            return None
        sem = guild.get(user_id)
        if sem is None:
            return None
        return sem

    def is_semaphore_locked(self, guild_id: int, user_id: int) -> bool:
        sem = self.get_user_semaphore(guild_id, user_id)
        if sem is not None and sem.semaphore.locked():
            return True
        return False

    @commands.hybrid_command(
        name="modmenu",
        brief="Open user moderation and punishment menu.",
        usage="<user/member>",
        aliases=['punish'],
        extras={
            'category': ModerationCategory,
        },
    )
    @app_commands.describe(user="Member or user you are trying to punish.")
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    async def moderation_menu_command(
        self,
        ctx: Context[Pidroid],
        user: discord.Member | discord.User
    ):
        assert ctx.guild
        assert isinstance(ctx.message.author, discord.Member)

        conf = await self.client.fetch_guild_configuration(ctx.guild.id)

        # Check initial permissions
        if not is_guild_moderator(ctx.message.author):
            raise BadArgument("You need to be a moderator to run this command!")

        if user.bot:
            raise BadArgument("You cannot punish bots, that would be pointless.")

        # Prevent moderator from punishing himself
        if user.id == ctx.message.author.id:
            raise BadArgument("You cannot punish yourself! That's what PHP is for.")

        # Generic check to only invoke the menu if author is a moderator
        is_moderator = isinstance(user, discord.Member) and is_guild_moderator(user)
        if is_moderator and not conf.allow_to_punish_moderators:
            raise BadArgument("You are not allowed to punish a moderator!")

        if isinstance(user, discord.Member) and user.top_role > ctx.guild.me.top_role:
            raise BadArgument("Specified member is above me!")

        if isinstance(user, discord.Member) and user.top_role == ctx.guild.me.top_role:
            raise BadArgument("Specified member shares the same role as I do, I cannot punish them!")

        if isinstance(user, discord.Member) and user.top_role >= ctx.message.author.top_role:
            raise BadArgument("Specified member is above or shares the same role with you!")
        
        sem = self.get_user_semaphore(ctx.guild.id, user.id)
        if sem is not None and sem.semaphore.locked():
            raise BadArgument(f"The moderation menu is already open for the user at {sem.message_url}")

        view = ModmenuView(
            api=self.client.api,
            ctx=ctx,
            configuration=conf,
            target=user,

            lock_fn=self.lock_punishment_menu,
            unlock_fn=self.unlock_punishment_menu,
            is_locked_fn=self.is_semaphore_locked
        )
        await view.initialize()
        msg = await ctx.reply(view=view)
        view.set_message(msg)

    @moderation_menu_command.error
    async def handle_moderation_menu_command_error(self, ctx: Context[Pidroid], error: Exception):
        if isinstance(error, MissingRequiredArgument):
            if error.param.name == "user":
                return await notify(ctx, "Please specify the member or the user you are trying to punish!")

        if isinstance(error, BadUnionArgument):
            if error.param.name == "user":
                for _err in error.errors:
                    if isinstance(_err, UserNotFound):
                        return await notify(ctx, str(_err))
        setattr(error, 'unhandled', True)

async def setup(client: Pidroid):
    await client.add_cog(ModerationCommandsCog(client))
