from __future__ import annotations

import asyncio

from datetime import timedelta
from dateutil.relativedelta import relativedelta # type: ignore
from discord import ui, ButtonStyle, Interaction
from discord.colour import Colour
from discord.user import User
from discord.embeds import Embed
from discord.emoji import Emoji
from discord.ext.commands.errors import BadArgument, MissingPermissions # type: ignore
from discord.member import Member
from discord.message import Message
from discord.partial_emoji import PartialEmoji
from discord.role import Role
from discord.utils import escape_markdown
from discord.ext import commands
from discord.ext.commands.context import Context # type: ignore
from discord.utils import get
from discord.file import File
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from pidroid.client import Pidroid
from pidroid.cogs.models.case import Ban, Kick, Timeout, Jail, Warning, remove_ban_from_context, remove_jail_from_context, remove_timeout_from_context
from pidroid.cogs.models.categories import ModerationCategory
from pidroid.cogs.models.exceptions import InvalidDuration, MissingUserPermissions
from pidroid.cogs.utils.decorators import command_checks
from pidroid.cogs.utils.embeds import PidroidEmbed
from pidroid.cogs.utils.file import Resource
from pidroid.cogs.utils.getters import get_role
from pidroid.cogs.utils.checks import check_junior_moderator_permissions, check_normal_moderator_permissions, check_senior_moderator_permissions, has_guild_permission, is_guild_moderator, is_guild_theotown, member_above_bot
from pidroid.cogs.utils.time import duration_string_to_relativedelta, utcnow

class ReasonModal(ui.Modal, title='Custom reason modal'):
    reason_input = ui.TextInput(label="Reason", placeholder="Please provide the reason") # type: ignore
    interaction: Interaction = None # type: ignore

    async def on_submit(self, interaction: Interaction):
        self.interaction = interaction
        self.stop()

class LengthModal(ui.Modal, title='Custom length modal'):
    length_input = ui.TextInput(label="Length", placeholder="Please provide the length") # type: ignore
    interaction: Interaction = None # type: ignore

    async def on_submit(self, interaction: Interaction):
        self.interaction = interaction
        self.stop()

class BaseButton(ui.Button):
    if TYPE_CHECKING:
        view: PunishmentInteraction

    def __init__(self, style: ButtonStyle, label: Optional[str], disabled: bool = False, emoji: Optional[Union[str, Emoji, PartialEmoji]] = None):
        super().__init__(style=style, label=label, disabled=disabled, emoji=emoji)

class ValueButton(BaseButton):
    def __init__(self, label: Optional[str], value: Optional[Any]):
        super().__init__(ButtonStyle.gray, label)
        # If value doesn't exist, mark it as custom
        if value is None:
            self.label = label or "Custom..."
            self.style = ButtonStyle.blurple
        # If value is -1, consider it permanent and therefore colour the button red
        elif value == -1:
            self.style = ButtonStyle.red
        self.value = value

class LengthButton(ValueButton):
    def __init__(self, label: Optional[str], value: Optional[Union[int, timedelta]]):
        super().__init__(label, value)

    async def callback(self, interaction: Interaction) -> None:
        value = self.value
        if value is None:
            value, interaction, timed_out = await self.view.custom_length_modal(interaction)

            if timed_out:
                return await interaction.response.send_message("Punishment reason modal has timed out!", ephemeral=True)

            if value is None:
                return await interaction.response.send_message("Punishment duration cannot be empty!", ephemeral=True)

            try:
                value = duration_string_to_relativedelta(value)
            except InvalidDuration as e:
                return await interaction.response.send_message(str(e), ephemeral=True)

            now = utcnow()
            delta: timedelta = now - (now - value)

            if delta.total_seconds() < 5 * 60:
                return await interaction.response.send_message("Punishment duration cannot be shorter than 5 minutes!", ephemeral=True)
            
            assert self.view._punishment is not None
            if self.view._punishment.type == "timeout":
                if delta.total_seconds() > 2419200: # 4 * 7 * 24 * 60 * 60
                    return await interaction.response.send_message("Timeouts cannot be longer than 4 weeks!", ephemeral=True)

        if self.view.is_finished():
            return await interaction.response.send_message("Interaction has timed out!", ephemeral=True)

        self.view._select_length(value)
        await self.view.create_reason_selector()
        await self.view._update_view(interaction)

class ReasonButton(ValueButton):
    def __init__(self, label: Optional[str], value: Optional[str]):
        super().__init__(label, value)

    async def callback(self, interaction: Interaction) -> None:
        value = self.value
        if value is None:
            value, interaction, timed_out = await self.view.custom_reason_modal(interaction)

            if timed_out:
                return await interaction.response.send_message("Punishment reason modal has timed out!", ephemeral=True)

            if value is None:
                return await interaction.response.send_message("Punishment reason cannot be empty!", ephemeral=True)

        if self.view.is_finished():
            return await interaction.response.send_message("Interaction has timed out!", ephemeral=True)

        self.view._select_reason(value)
        await self.view.create_confirmation_selector()
        await self.view._update_view(interaction)

class ConfirmButton(BaseButton):
    def __init__(self):
        super().__init__(ButtonStyle.green, "Confirm")

    async def callback(self, interaction: Interaction) -> None:
        await self.view._handle_confirmation(interaction, True)

class CancelButton(BaseButton):
    def __init__(self):
        super().__init__(ButtonStyle.red, "Cancel")

    async def callback(self, interaction: Interaction) -> None:
        await self.view._handle_confirmation(interaction, False)

class BasePunishmentButton(ui.Button):
    if TYPE_CHECKING:
        view: PunishmentInteraction

    def __init__(self, style: ButtonStyle, label: str, enabled: bool = True, emoji: Optional[Union[str, Emoji, PartialEmoji]] = None):
        super().__init__(style=style, label=label, disabled=not enabled, emoji=emoji)

class BanButton(BasePunishmentButton):
    def __init__(self, enabled: bool = True):
        super().__init__(ButtonStyle.red, "Ban", enabled, "🔨")

    async def callback(self, interaction: Interaction) -> None:
        self.view._select_type(Ban(self.view.ctx, self.view.user))
        await self.view.create_length_selector()
        await self.view._update_view(interaction)

class UnbanButton(BasePunishmentButton):
    def __init__(self, enabled: bool = True):
        super().__init__(ButtonStyle.red, "Unban", enabled, "🔨")

    async def callback(self, interaction: Interaction) -> None:
        await remove_ban_from_context(
            self.view.ctx, self.view.user,
            f"Unbanned by {str(self.view.ctx.author)}"
        )
        await self.view.finish(interaction)

class KickButton(BasePunishmentButton):
    def __init__(self, enabled: bool = True):
        super().__init__(ButtonStyle.gray, "Kick", enabled)

    async def callback(self, interaction: Interaction) -> None:
        assert isinstance(self.view.user, Member)
        self.view._select_type(Kick(self.view.ctx, self.view.user))
        await self.view.create_reason_selector()
        await self.view._update_view(interaction)

class JailButton(BasePunishmentButton):
    def __init__(self, enabled: bool = True):
        super().__init__(ButtonStyle.gray, "Jail", enabled)

    async def callback(self, interaction: Interaction) -> None:
        assert isinstance(self.view.user, Member)
        self.view._select_type(Jail(self.view.ctx, self.view.user))
        await self.view.create_reason_selector()
        await self.view._update_view(interaction)

class KidnapButton(BasePunishmentButton):
    def __init__(self, enabled: bool = True):
        super().__init__(ButtonStyle.gray, "Kidnap", enabled)

    async def callback(self, interaction: Interaction) -> None:
        assert isinstance(self.view.user, Member)
        self.view._select_type(Jail(self.view.ctx, self.view.user, True))
        await self.view.create_reason_selector()
        await self.view._update_view(interaction)

class RemoveJailButton(BasePunishmentButton):
    def __init__(self, enabled: bool = True):
        super().__init__(ButtonStyle.gray, "Release from jail", enabled)

    async def callback(self, interaction: Interaction) -> None:
        assert isinstance(self.view.user, Member)
        assert self.view.jail_role is not None
        await remove_jail_from_context(
            self.view.ctx, self.view.user,
            self.view.jail_role,
            f"Released by {str(self.view.ctx.author)}"
        )
        await self.view.finish(interaction)

class TimeoutButton(BasePunishmentButton):
    def __init__(self, enabled: bool = True):
        super().__init__(ButtonStyle.gray, "Time-out", enabled)

    async def callback(self, interaction: Interaction) -> None:
        assert isinstance(self.view.user, Member)
        self.view._select_type(Timeout(self.view.ctx, self.view.user))
        await self.view.create_length_selector()
        await self.view._update_view(interaction)

class RemoveTimeoutButton(BasePunishmentButton):
    def __init__(self, enabled: bool = True):
        super().__init__(ButtonStyle.gray, "Remove time-out", enabled)

    async def callback(self, interaction: Interaction) -> None:
        assert isinstance(self.view.user, Member)
        await remove_timeout_from_context(
            self.view.ctx, self.view.user,
            f"Removed by {str(self.view.ctx.author)}"
        )
        await self.view.finish(interaction)

class WarnButton(BasePunishmentButton):
    def __init__(self, enabled: bool = True):
        super().__init__(ButtonStyle.gray, "Warn", enabled, "⚠️")

    async def callback(self, interaction: Interaction) -> None:
        assert isinstance(self.view.user, Member)
        self.view._select_type(Warning(self.view.ctx, self.view.user))
        await self.view.create_reason_selector()
        await self.view._update_view(interaction)


LENGTH_MAPPING = {
    "timeout": [
        LengthButton("30 minutes", timedelta(minutes=30)),
        LengthButton("An hour", timedelta(hours=1)),
        LengthButton("2 hours", timedelta(hours=2)),
        LengthButton("12 hours", timedelta(hours=12)),
        LengthButton("A day", timedelta(hours=24)),
        LengthButton("A week", timedelta(weeks=1)),
        LengthButton("4 weeks (max)", timedelta(weeks=4)),
        LengthButton(None, None)
    ],
    "ban": [
        LengthButton("24 hours", timedelta(hours=24)),
        LengthButton("A week", timedelta(weeks=1)),
        LengthButton("2 weeks", timedelta(weeks=2)),
        LengthButton("A month", timedelta(days=30)),
        LengthButton("Permanent", -1),
        LengthButton(None, None)
    ]
}

REASON_MAPPING = {
    "ban": [
        ReasonButton("Ignoring moderator's orders", "Ignoring moderator's orders."),
        ReasonButton("Hacked content", "Sharing hacked content."),
        ReasonButton("Offensive content or hate-speech", "Posting offensive content or hate-speech."),
        ReasonButton("Underage user", "You are under the allowed age as defined in Discord's Terms of Service."),
        ReasonButton("Harassing other members", "Harassing other members."),
        ReasonButton("Scam or phishing", "Sharing scams or phishing content."),
        ReasonButton("Continued offences", "Continued and or repeat offences."),
        ReasonButton(None, None)
    ],
    "kick": [
        ReasonButton("Underage", "You are under the allowed age as defined in Discord's Terms of Service. Please rejoin when you're older."),
        ReasonButton("Alternative account", "Alternative accounts are not allowed."),
        ReasonButton(None, None)
    ],
    "jail": [
        ReasonButton("Pending investigation", "Pending investigation."),
        ReasonButton("Questioning", "Questioning."),
        ReasonButton(None, None)
    ],
    "timeout": [
        ReasonButton("Being emotional or upset", "Being emotional or upset."),
        ReasonButton("Spam", "Spam."),
        ReasonButton("Disrupting the chat", "Disrupting the chat."),
        ReasonButton(None, None)
    ],
    "warning": [
        ReasonButton("Spam", "Spam"),
        ReasonButton("Failure to follow orders", "Failure to follow orders."),
        ReasonButton("Failure to comply with verbal warning", "Failure to comply with a verbal warning."),
        ReasonButton("Hateful content", "Sharing hateful content."),
        ReasonButton("Repeat use of wrong channels", "Repeat use of wrong channels."),
        ReasonButton("NSFW content", "Sharing of NSFW content."),
        ReasonButton("Politics", "Politics and or political content."),
        ReasonButton(None, None)
    ]
}

class PunishmentInteraction(ui.View):

    if TYPE_CHECKING:
        _message: Optional[Message]

    def __init__(self, cog: ModeratorCommands, ctx: Context, user: Union[Member, User], embed: Embed):
        super().__init__(timeout=300)
        self.cog = cog
        self.ctx = ctx
        self.user = user
        self.embed = embed
        self._message = None

        self._punishment: Optional[Union[Ban, Kick, Jail, Timeout, Warning]] = None

        self.jail_role: Optional[Role] = None

    async def initialize(self):
        client = self.ctx.bot
        assert isinstance(client, Pidroid)
        c = client.get_guild_configuration(self.ctx.guild.id)
        assert c is not None
        role = get_role(self.ctx.guild, c.jail_role)
        if role is not None:
            self.jail_role = role

        # Lock the punishment menu with a semaphore
        await self.cog.lock_punishment_menu(self.ctx.guild.id, self.user.id)

    def set_reply_message(self, message: Message) -> None:
        """Sets the reply message to which this interaction belongs to."""
        self._message = message

    """Private utility methods"""

    def _select_type(self, instance):
        self.embed.description = f"Type: {str(instance)}"
        self._punishment = instance

    def _select_length(self, length: Union[int, timedelta, relativedelta]):
        # Special case
        if length == -1:
            length = None

        assert self._punishment is not None
        self._punishment.set_length(length)
        assert isinstance(self.embed.description, str)
        self.embed.description += f"\nLength: {self._punishment.length_as_string}"

    def _select_reason(self, reason: str):
        assert isinstance(self.embed.description, str)
        self.embed.description += f"\nReason: {reason}"
        assert self._punishment is not None
        self._punishment.reason = reason

    async def _update_view(self, interaction: Optional[Interaction]) -> None:
        if interaction is None:
            assert self._message is not None
            await self._message.edit(embed=self.embed, view=self)
        else:
            await interaction.response.edit_message(embed=self.embed, view=self)

    """Checks"""

    async def is_user_banned(self) -> bool:
        """Returns true if user is currently banned."""
        try:
            await self.ctx.guild.fetch_ban(self.user)
            return True
        except Exception:
            return False

    async def is_user_jailed(self) -> bool:
        """Returns true if user is currently jailed."""
        if isinstance(self.user, User) or self.jail_role is None:
            return False
        client: Pidroid = self.ctx.bot
        return (
            get(self.ctx.guild.roles, id=self.jail_role.id) in self.user.roles
            and await client.api.is_currently_jailed(self.ctx.guild.id, self.user.id)
        )

    async def is_user_timed_out(self) -> bool:
        """Returns true if user is currently muted."""
        if isinstance(self.user, User):
            return False
        return self.user.is_timed_out()

    """
    Permission checks for moderators and Pidroid
    """

    def is_junior_moderator(self, **perms) -> bool:
        try:
            check_junior_moderator_permissions(self.ctx, **perms)
            return True
        except (MissingUserPermissions, MissingPermissions):
            return False

    def is_normal_moderator(self, **perms) -> bool:
        try:
            check_normal_moderator_permissions(self.ctx, **perms)
            return True
        except (MissingUserPermissions, MissingPermissions):
            return False

    def is_senior_moderator(self, **perms) -> bool:
        try:
            check_senior_moderator_permissions(self.ctx, **perms)
            return True
        except (MissingUserPermissions, MissingPermissions):
            return False

    """
    Methods for creating button interfaces for:
    - Selecting punishment type
    - Selecting punishment length
    - Selecting punishment reason
    - Confirming or cancelling the action
    """

    async def custom_reason_modal(self, interaction: Interaction) -> Tuple[Optional[str], Interaction, bool]:
        modal = ReasonModal()
        await interaction.response.send_modal(modal)
        timed_out = await modal.wait()
        if timed_out:
            await self.timeout_interface(interaction)
        return modal.reason_input.value, modal.interaction, timed_out

    async def custom_length_modal(self, interaction: Interaction) -> Tuple[Optional[str], Interaction, bool]:
        modal = LengthModal()
        await interaction.response.send_modal(modal)
        timed_out = await modal.wait()
        if timed_out:
            await self.timeout_interface(interaction)
        return modal.length_input.value, modal.interaction, timed_out

    async def create_type_selector(self):
        self.embed.set_footer(text="Select the punishment type")
        self.clear_items()
        is_member = isinstance(self.user, Member)

        # Store permission checks here
        has_ban_permission = (
            self.is_normal_moderator(ban_members=True)
            and has_guild_permission(self.ctx.me, "ban_members")
        )
        has_unban_permission = (
            self.is_senior_moderator(ban_members=True)
            and has_guild_permission(self.ctx.me, "ban_members")
        )
        has_kick_permission = (
            self.is_junior_moderator(kick_members=True)
            and has_guild_permission(self.ctx.me, "kick_members")
        )
        has_timeout_permission = has_guild_permission(self.ctx.me, "moderate_members")
        has_jail_permission = has_guild_permission(self.ctx.me, "manage_roles")

        # Add ban/unban buttons
        if not await self.is_user_banned():
            self.add_item(BanButton(has_ban_permission))
        else:
            self.add_item(UnbanButton(has_unban_permission))

        # Kick button
        self.add_item(KickButton(is_member and has_kick_permission))

        # Add jail/unjail buttons
        if not await self.is_user_jailed():
            self.add_item(JailButton(is_member and self.jail_role is not None and has_jail_permission))
            if is_guild_theotown(self.ctx.guild):
                self.add_item(KidnapButton(is_member and self.jail_role is not None and has_jail_permission))
        else:
            self.add_item(RemoveJailButton(has_jail_permission))

        # Add timeout/un-timeout buttons
        if not await self.is_user_timed_out():
            self.add_item(TimeoutButton(is_member and has_timeout_permission))
        else:
            self.add_item(RemoveTimeoutButton(has_timeout_permission))

        # Warn button
        self.add_item(WarnButton(is_member))

        self.add_item(CancelButton())

    async def create_length_selector(self):
        # Acquire mapping for lengths for punishment types
        mapping: List[ValueButton] = LENGTH_MAPPING.get(str(self._punishment), None)
        if mapping is None or len(mapping) == 0:
            return await self.create_reason_selector()

        self.clear_items()
        for button in mapping:
            self.add_item(button)
        self.add_item(CancelButton())
        self.embed.set_footer(text="Select the punishment length")

    async def create_reason_selector(self):
        # Acquire mapping for lengths for punishment types
        mapping: List[ValueButton] = REASON_MAPPING.get(str(self._punishment), None)
        if mapping is None or len(mapping) == 0:
            return await self.create_confirmation_selector()

        self.clear_items()
        for button in mapping:
            self.add_item(button)
        self.add_item(CancelButton())
        self.embed.set_footer(text="Select reason for the punishment")

    async def create_confirmation_selector(self):
        self.clear_items()
        self.add_item(ConfirmButton())
        self.add_item(CancelButton())
        self.embed.set_footer(text="Confirm or cancel the punishment")

    """Handle selections"""

    async def _handle_confirmation(self, interaction: Interaction, confirmed: bool):
        self.embed.remove_footer()

        # If moderator confirmed the action
        if confirmed:
            assert self._punishment is not None
            if self._punishment.type == "jail":
                assert isinstance(self._punishment, Jail)
                assert self.jail_role is not None
                await self._punishment.issue(self.jail_role)
            else:
                assert isinstance(self._punishment, (Ban, Kick, Timeout, Warning))
                await self._punishment.issue()
            self.remove_items()
            return await self.finish(interaction)

        # Otherwise, cancel the interaction
        await self.cancel_interface(interaction)

    """Clean up related methods"""

    async def timeout_interface(self, interaction: Optional[Interaction]) -> None:
        self.embed.set_footer(text="Punishment creation has timed out")
        self.embed.colour = Colour.red()
        self.remove_items()
        await self._update_view(interaction)
        self.stop()
        self.cog.unlock_punishment_menu(self.ctx.guild.id, self.user.id)

    async def cancel_interface(self, interaction: Interaction) -> None:
        self.embed.set_footer(text="Punishment creation has been cancelled")
        self.embed.colour = Colour.red()
        self.remove_items()
        await self._update_view(interaction)
        self.stop()
        self.cog.unlock_punishment_menu(self.ctx.guild.id, self.user.id)

    def remove_items(self) -> None:
        """Removes all items from the view."""
        for child in self.children.copy():
            self.remove_item(child)

    async def finish(self, interaction: Interaction) -> None:
        """Causes the view to remove itself and stop listening to interactions."""
        # Stop responding to interactions
        self.stop()
        # Unlock semaphore
        self.cog.unlock_punishment_menu(self.ctx.guild.id, self.user.id)
        # Respond to defer
        await interaction.response.defer()
        # Delete original message if it exists
        if interaction.message:
            await interaction.message.delete()

    def stop(self) -> None:
        """Stops listening to all interactions for this view."""
        self.remove_items()
        return super().stop()

    async def on_timeout(self) -> None:
        """Called when view times out."""
        await self.timeout_interface(None)

    async def interaction_check(self, interaction: Interaction) -> bool:
        """Ensure that the interaction is called by the message author.

        Moderator, in this case."""
        if interaction.user and interaction.user.id == self.ctx.author.id:
            return True
        await interaction.response.send_message('This menu cannot be controlled by you, sorry!', ephemeral=True)
        return False


class ModeratorCommands(commands.Cog): # type: ignore
    """This class implements cog which contains commands for moderation."""

    def __init__(self, client: Pidroid):
        self.client = client
        # GUILD_ID: {USER_ID: Semaphore}
        self.user_semaphores: Dict[int, Dict[int, asyncio.Semaphore]] = {}

    def _create_semaphore_if_not_exist(self, guild_id: int, user_id: int) -> asyncio.Semaphore:
        if self.user_semaphores.get(guild_id) is None:
            self.user_semaphores[guild_id] = {}
        user = self.user_semaphores[guild_id].get(user_id)
        if user is None:
            self.user_semaphores[guild_id][user_id] = asyncio.Semaphore(1)
        return self.user_semaphores[guild_id][user_id]

    async def lock_punishment_menu(self, guild_id: int, user_id : int) -> None:
        sem = self._create_semaphore_if_not_exist(guild_id, user_id)
        await sem.acquire()

    def unlock_punishment_menu(self, guild_id: int, user_id: int) -> None:
        sem = self._create_semaphore_if_not_exist(guild_id, user_id)
        sem.release()
        # Save memory with this simple trick
        self.user_semaphores[guild_id].pop(user_id)

    def is_user_being_punished(self, guild_id: int, user_id: int) -> bool:
        guild = self.user_semaphores.get(guild_id)
        if guild is None:
            return False
        sem = guild.get(user_id)
        if sem is None:
            return False
        return sem.locked()

    @commands.command( # type: ignore
        brief='Removes a specified amount of messages from the channel.',
        usage='<amount>',
        category=ModerationCategory
    )
    @commands.bot_has_permissions(manage_messages=True, send_messages=True) # type: ignore
    @command_checks.can_purge()
    @commands.guild_only() # type: ignore
    async def purge(self, ctx: Context, amount: int = 0):
        if amount <= 0:
            raise BadArgument("Please specify the amount of messages to delete!")

        # Evan proof
        if amount > 1000:
            raise BadArgument("Max amount of messages I can purge at once is 1000!")

        await ctx.channel.purge(limit=amount + 1)
        await ctx.send(f'{amount} messages have been purged!', delete_after=1.5)

    @commands.command(hidden=True) # type: ignore
    @commands.bot_has_permissions(manage_messages=True, send_messages=True, attach_files=True) # type: ignore
    @command_checks.is_junior_moderator(manage_messages=True)
    @commands.guild_only() # type: ignore
    async def deletethis(self, ctx: Context):
        await ctx.message.delete(delay=0)
        await ctx.channel.purge(limit=1)
        await ctx.send(file=File(Resource('delete_this.png')))

    # TODO: add proper permission checks for both, the bot and the end user (mod)
    @commands.command( # type: ignore
        brief="Open user moderation and punishment menu.",
        usage="<user/member>",
        category=ModerationCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @command_checks.guild_configuration_exists()
    @commands.guild_only() # type: ignore
    async def punish(self, ctx: Context, user: Union[Member, User] = None):
        # Check initial permissions
        if not is_guild_moderator(ctx.guild, ctx.channel, ctx.message.author):
            raise BadArgument("You need to be a moderator to run this command!")

        if user is None:
            raise BadArgument("Please specify the member or the user you are trying to punish!")

        if isinstance(user, Member) and member_above_bot(ctx.guild, user):
            raise BadArgument("Specified member is above me!")

        if self.is_user_being_punished(ctx.guild.id, user.id):
            raise BadArgument("The punishment menu is already open for the user.")

        # Prevent moderator from punishing himself
        if user.id == ctx.message.author.id:
            raise BadArgument("You cannot punish yourself! That's what PHP is for.")

        # Generic check to only invoke the menu if author is a moderator
        if is_guild_moderator(ctx.guild, ctx.channel, user):
            raise BadArgument("You cannot punish a moderator!")

        # Create an embed overview
        embed = PidroidEmbed()
        embed.title = f"Punish {escape_markdown(str(user))}"

        view = PunishmentInteraction(self, ctx, user, embed)
        await view.initialize()
        await view.create_type_selector()

        message = await ctx.reply(embed=embed, view=view)
        view.set_reply_message(message)

    @commands.command( # type: ignore
        brief='Suspends member\'s ability to send messages for a week.\nIt is recommended to be used to rapidly stop spam or chat flood.',
        usage='<member>',
        category=ModerationCategory
    )
    @commands.bot_has_permissions(manage_messages=True, send_messages=True, moderate_members=True) # type: ignore
    @command_checks.is_junior_moderator(moderate_members=True)
    @command_checks.guild_configuration_exists()
    @commands.guild_only() # type: ignore
    async def suspend(self, ctx: Context, *, member: Member):
        t = Timeout(ctx, member)
        t.reason = "Suspended communications"
        t.set_length(timedelta(days=7))
        await t.issue()
        await ctx.message.delete(delay=0)

async def setup(client: Pidroid):
    await client.add_cog(ModeratorCommands(client))
