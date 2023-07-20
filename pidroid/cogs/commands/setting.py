from __future__ import annotations

import discord
import re
import logging

from contextlib import suppress
from discord import AllowedMentions, Colour, Interaction, NotFound, TextChannel, Role
from discord.emoji import Emoji
from discord.enums import ButtonStyle
from discord.ext import commands # type: ignore
from discord.ext.commands.context import Context # type: ignore
from discord.ext.commands.errors import BadArgument
from discord.interactions import Interaction
from discord.partial_emoji import PartialEmoji # type: ignore
from typing import TYPE_CHECKING, Dict, List, Optional, Type, Union

from pidroid.client import Pidroid
from pidroid.models.categories import AdministrationCategory, UtilityCategory
from pidroid.models.guild_configuration import GuildConfiguration
from pidroid.models.setting_ui import BooleanSetting, ChannelSetting, NumberSetting, ReadonlySetting, RoleSetting, Submenu, TextButton, TextModal, TextSetting
from pidroid.utils.embeds import PidroidEmbed, SuccessEmbed

logger = logging.getLogger('Pidroid')

SETUP_REASON = "Server jail system setup"

# https://www.geeksforgeeks.org/check-if-an-url-is-valid-or-not-using-regular-expression/
URL_REGEX = re.compile(
    "((http|https)://)(www.)?"
    "[a-zA-Z0-9@:%._\\+~#?&//=]"
    "{2,256}\\.[a-z]"
    "{2,6}\\b([-a-zA-Z0-9@:%"
    "._\\+~#?&//=]*)"
)

FORBIDDEN_PREFIXES = [',', '\\', '/']

class ChangePrefixesButton(TextButton):

    def __init__(self, *, style: ButtonStyle = ButtonStyle.secondary, label: str | None = None, disabled: bool = False, emoji: str | Emoji | PartialEmoji | None = None, callback):
        super().__init__(style=style, label=label, disabled=disabled, emoji=emoji, callback=callback)

    def create_modal(self) -> TextModal:
        modal = TextModal(title=self.label, timeout=120)
        modal.add_item(discord.ui.TextInput(
            label="Prefixes", placeholder="Provide uh, anyway",
            required=False
        ))
        return modal

    async def handle_input(self, modal: TextModal):
        raw_value = modal.children[0].value.strip()

        if raw_value == ",":
            return await modal.interaction.response.send_message(
                "Comma is a forbidden character.",
                ephemeral=True
            )

        split_values = raw_value.split(',')
        
        # Limit prefixes
        if len(split_values) > 5:
            return await modal.interaction.response.send_message(
                "You can only define up to 5 prefixes.",
                ephemeral=True
            )
        
        cleaned_prefixes: List[str] = []
        for value in split_values:
            stripped = value.strip()
            if stripped == "":
                continue
            if stripped in FORBIDDEN_PREFIXES:
                return await modal.interaction.response.send_message(
                    f"'{stripped}' is a forbidden character.",
                    ephemeral=True
                )
            if len(stripped) > 5:
                return await modal.interaction.response.send_message(
                    f"For best user experience, please keep prefix '{stripped}' below 5 characters.",
                    ephemeral=True
                )
            cleaned_prefixes.append(stripped)
            
        if len(cleaned_prefixes) == 0:
            return await modal.interaction.response.send_message(
                "You did not specify any valid prefixes.",
                ephemeral=True
            )

        await self._callback(cleaned_prefixes)
        await self.view.refresh_menu(modal.interaction)


class ChangeBanAppealUrlButton(TextButton):

    def __init__(self, *, style: ButtonStyle = ButtonStyle.secondary, label: str | None = None, disabled: bool = False, emoji: str | Emoji | PartialEmoji | None = None, callback):
        super().__init__(style=style, label=label, disabled=disabled, emoji=emoji, callback=callback)

    def create_modal(self) -> TextModal:
        modal = TextModal(title=self.label, timeout=120)
        modal.add_item(discord.ui.TextInput(
            label="Ban appeal URL", placeholder="Provide a valid url or nothing to remove it.",
            required=False
        ))
        return modal

    async def handle_input(self, modal: TextModal):
        url = modal.children[0].value.strip()

        # Clear URL
        if url == '':
            await self._callback(None)
            return await self.view.refresh_menu(modal.interaction)

        # If URL is valid
        if re.search(URL_REGEX, url):
            await self._callback(url)
            return await self.view.refresh_menu(modal.interaction)

        # If URL is not valid
        await modal.interaction.response.send_message(
            "The URL that you have provided is not a valid URL.",
            ephemeral=True
        )

class XpMultiplierButton(TextButton):

    def __init__(self, *, style: ButtonStyle = ButtonStyle.secondary, label: str | None = None, disabled: bool = False, emoji: str | Emoji | PartialEmoji | None = None, callback):
        super().__init__(style=style, label=label, disabled=disabled, emoji=emoji, callback=callback)

    def create_modal(self) -> TextModal:
        modal = TextModal(title=self.label, timeout=120)
        modal.add_item(discord.ui.TextInput(
            label="XP multiplier", placeholder="Provide a floating point value between 0 and 2."
        ))
        return modal

    async def handle_input(self, modal: TextModal):
        value = modal.children[0].value.strip().replace(",", ".")

        # Try converting value into a float
        try:
            value_as_float = float(value)
        except ValueError:
            return await modal.interaction.response.send_message(
                "The value that you entered is not a valid float.",
                ephemeral=True
            )
        
        # If value is outside the range
        if value_as_float > 2 or value_as_float < 0:
            return await modal.interaction.response.send_message(
                "Value is outside the specified range of 0 ≤ x ≤ 2",
                ephemeral=True
            )
        
        # Otherwise, accept it
        await self._callback(round(value_as_float, 2))
        await self.view.refresh_menu(modal.interaction)

class SubmenuSelect(discord.ui.Select):

    if TYPE_CHECKING:
        view: GuildConfigurationView

    def __init__(self) -> None:
        super().__init__(placeholder="Select submenu", options=SUBMENU_OPTIONS)

    async def callback(self, interaction: Interaction):
        success = await self.view.change_menu(interaction, self.values[0])
        if not success:
            await interaction.response.send_message("You selected a menu that does not exist!", ephemeral=True)

class CloseButton(discord.ui.Button):

    if TYPE_CHECKING:
        view: GuildConfigurationView

    def __init__(self):
        super().__init__(style=discord.ButtonStyle.red, label="Close")

    async def callback(self, interaction: Interaction):
        await self.view.close_interface(interaction)

class GeneralSubmenu(Submenu):

    def __init__(self, *, configuration: GuildConfiguration) -> None:
        prefixes = configuration.guild_prefixes.prefixes or configuration.api.client.prefixes
        settings=[
            TextSetting(
                cls=ChangePrefixesButton,
                name="Prefixes",
                value=', '.join(prefixes),
                label="Change prefixes",
                callback=configuration.update_prefixes
            ),
            BooleanSetting(
                name="Everyone can manage tags",
                value=configuration.public_tags,
                label_true="Allow everyone to manage tags",
                label_false="Don't allow everyone to manage tags",
                callback=configuration.toggle_public_tags
            ),
        ]
        super().__init__(
            name="General settings",
            description="This submenu contains general settings related to the functioning of Pidroid within this server.",
            settings=settings
        )

class ModerationSubmenu(Submenu):

    def __init__(self, *, configuration: GuildConfiguration) -> None:
        settings=[
            RoleSetting(
                name="Jail role",
                value=configuration.jail_role_id,
                configuration=configuration,
                placeholder="Change jail role",
                callback=configuration.update_jail_role_id
            ),
            ChannelSetting(
                name="Jail channel",
                value=configuration.jail_channel_id,
                configuration=configuration,
                channel_types=[discord.ChannelType.text],
                placeholder="Change jail channel",
                callback=configuration.update_jail_channel_id
            ),
            BooleanSetting(
                name="Allow to punish moderators",
                value=configuration.allow_to_punish_moderators,
                label_true="Allow to punish moderators",
                label_false="Don't allow to punish moderators",
                callback=configuration.toggle_moderator_punishing
            ),
            TextSetting(
                cls=ChangeBanAppealUrlButton,
                name="Ban appeal URL",
                value=configuration.appeal_url,
                label="Change ban appeal URL",
                callback=configuration.update_appeal_url
            )
        ]
        super().__init__(
            name="Moderation settings",
            description="This submenu contains settings related to the Pidroid's punishment and moderation system.",
            settings=settings
        )
        
class LevelingSubmenu(Submenu):

    def __init__(self, *, configuration: GuildConfiguration) -> None:
        assert configuration.guild is not None
        # Store xp exempt channel mentions
        channels = []
        for c_id in configuration.xp_exempt_channels:
            chan = configuration.guild.get_channel(c_id)
            if chan:
                channels.append(chan.mention)
        # Store xp exempt role mentions
        roles = []
        for r_id in configuration.xp_exempt_roles:
            role = configuration.guild.get_role(r_id)
            if role:
                roles.append(role.mention)
        settings=[
            BooleanSetting(
                name="Leveling system active",
                value=configuration.xp_system_active,
                label_true="Enable leveling system",
                label_false="Disable leveling system",
                callback=configuration.toggle_xp_system
            ),
            NumberSetting(
                cls=XpMultiplierButton,
                name="XP multiplier",
                value=configuration.xp_multiplier,
                label="Change XP multiplier",
                callback=configuration.update_xp_multiplier
            ),
            ReadonlySetting(
                name="XP exempt channels",
                description="You can manage this setting with a subcommand.",
                value=','.join(channels) if channels else None
            ),
            ReadonlySetting(
                name="XP exempt roles",
                description="You can manage this setting with a subcommand.",
                value=','.join(roles) if roles else None
            ),
            BooleanSetting(
                name="XP rewards stacked",
                value=configuration.level_rewards_stacked,
                label_true="Enable level reward stacking",
                label_false="Disable level reward stacking",
                callback=configuration.toggle_level_reward_stacking
            ),
        ]
        super().__init__(
            name="Leveling settings",
            description="This submenu contains settings related to Pidroid's XP and level rewards system.",
            settings=settings
        )

class SuggestionSubmenu(Submenu):

    def __init__(self, *, configuration: GuildConfiguration) -> None:
        settings=[
            BooleanSetting(
                name="Suggestion system active",
                value=configuration.suggestion_system_active,
                label_true="Enable suggestion system",
                label_false="Disable suggestion system",
                callback=configuration.toggle_suggestion_system
            ),
            BooleanSetting(
                name="Create threads for suggestions",
                value=configuration.suggestion_threads_enabled,
                label_true="Enable threads for suggestions",
                label_false="Disable threads for suggestions",
                callback=configuration.toggle_suggestion_threads,
                disabled=True
            ),
            ChannelSetting(
                name="Suggestion channel",
                value=configuration.suggestions_channel_id,
                configuration=configuration,
                channel_types=[discord.ChannelType.text],
                placeholder="Change suggestion channel",
                callback=configuration.update_suggestions_channel_id
            ),
        ]
        super().__init__(
            name="Suggestion settings",
            description="This submenu contains settings related to Pidroid's suggestion system.",
            settings=settings
        )

SUBMENUS: Dict[
    str,
    Union[
        Type[GeneralSubmenu],
        Type[ModerationSubmenu],
        Type[LevelingSubmenu],
        Type[SuggestionSubmenu],
        None
    ]
] = {
    "general": GeneralSubmenu,
    "moderation": ModerationSubmenu,
    "leveling": LevelingSubmenu,
    "suggestion": SuggestionSubmenu,
}

SUBMENU_OPTIONS = [
    discord.SelectOption(label="General settings", value="general"),
    discord.SelectOption(label="Moderation settings", value="moderation"),
    discord.SelectOption(label="Leveling settings", value="leveling"),
    discord.SelectOption(label="Suggestion system", value="suggestion")
]

class GuildConfigurationView(discord.ui.View):

    def __init__(self, client: Pidroid, ctx: Context, *, timeout: float = 600):
        super().__init__(timeout=timeout)
        self.__client = client
        self.__ctx = ctx
        self.__embed = PidroidEmbed()
        self.__current_submenu: Optional[str] = None
        self._reset_view()

    def _reset_view(self) -> None:
        """Resets the message to initial state."""
        self.__embed = PidroidEmbed(
            title="Server configuration manager",
            description=(
                "You can use this menu to manage Pidroid related settings for your server. "
                "You can change settings by navigating to submenus as provided in the selector down below."
            )
        )
        self.add_item(SubmenuSelect())
        self.add_item(CloseButton())

    async def send(self) -> None:
        """Sends the message with the configuration view."""
        self.__message = await self.__ctx.reply(embed=self.__embed, view=self)

    async def refresh_menu(self, interaction: Interaction):
        """Refreshes the current menu state."""
        if self.__current_submenu is not None:
            return await self.change_menu(interaction, self.__current_submenu)
        self._reset_view()
        await self._update_view(interaction)

    async def change_menu(self, interaction: Interaction, submenu_name: str) -> bool:
        """Changes menu to the specified one. Returns boolean denoting whether operation was successful."""
        self.__current_submenu = submenu_name

        # Acquire the submenu type, if not available,
        # send an error to the user
        submenu = SUBMENUS.get(submenu_name, None)
        if submenu is None:
            return False
        
        # Acquire latest guild configuration
        assert self.__ctx.guild is not None
        config = await self.__client.fetch_guild_configuration(self.__ctx.guild.id)
        
        menu = submenu(configuration=config)

        self.__embed = menu.embed
        self.clear_items()
        self.add_item(SubmenuSelect())
        for item in menu.items:
            self.add_item(item)
        self.add_item(CloseButton())

        # Update the view
        await self._update_view(interaction)
        return True

    async def close_interface(self, interaction: Interaction) -> None:
        """Called to clean up when the interface is closed by the user."""
        await self.__message.delete()
        await interaction.response.send_message("Settings menu has been closed.", ephemeral=True)

    async def timeout_interface(self, interaction: Optional[Interaction]) -> None:
        """Called to clean up when the interaction or interface timed out."""
        self.__embed.set_footer(text="Settings menu has timed out")
        self.__embed.colour = Colour.red()
        await self.finish_interface(interaction)

    async def error_interface(self, interaction: Optional[Interaction]) -> None:
        """Called to clean up when an error is encountered."""
        self.__embed.set_footer(text="Settings menu has encountered an unexpected error")
        self.__embed.colour = Colour.red()
        await self.finish_interface(interaction)

    async def finish_interface(
        self,
        interaction: Optional[Interaction],
        embed: Optional[PidroidEmbed] = None
    ) -> None:
        """Removes all buttons and updates the interface. No more calls can be done to the interface."""
        # Remove all items
        for child in self.children.copy():
            self.remove_item(child)

        # If embed is provided, update it
        if embed:
            self.__embed = embed
        await self._update_view(interaction) # Update message with latest information
        self.stop() # Stop responding to any interaction

    async def _update_view(self, interaction: Optional[Interaction]) -> None:
        """Updates the original interaction response message.
        
        If interaction object is not provided, then the message itself will be edited."""
        if interaction is None:
            with suppress(NotFound):
                await self.__message.edit(embed=self.__embed, view=self)
        else:
            await interaction.response.edit_message(embed=self.__embed, view=self)

    """Event listeners"""

    async def on_timeout(self) -> None:
        """Called when view times out."""
        await self.timeout_interface(None)

    async def on_error(self, interaction: Interaction, error: Exception, item: discord.ui.Item) -> None:
        """Called when view catches an error."""
        logger.exception(error)
        logger.error(f"The above exception is caused by {str(item)} item")
        if interaction.response.is_done():
            await interaction.followup.send('An unknown error occurred, sorry', ephemeral=True)
        else:
            await interaction.response.send_message('An unknown error occurred, sorry', ephemeral=True)

        await self.error_interface(None)

    async def interaction_check(self, interaction: Interaction) -> bool:
        """Ensure that the interaction is called by the message author."""
        if interaction.user and interaction.user.id == self.__ctx.author.id:
            return True
        await interaction.response.send_message('This menu cannot be controlled by you!', ephemeral=True)
        return False

class SettingsCommands(commands.Cog): # type: ignore
    """This class implements cog which contains administrator commands for Pidroid configuration management."""

    def __init__(self, client: Pidroid):
        self.client = client

    @commands.hybrid_group( # type: ignore
        name="configure",
        brief="Allows to manage server bot configuration.",
        category=AdministrationCategory,
        invoke_without_command=True,
        fallback="menu"
    )
    @commands.bot_has_guild_permissions(send_messages=True) # type: ignore
    @commands.has_permissions(manage_guild=True) # type: ignore
    @commands.guild_only() # type: ignore
    async def configure_command(self, ctx: Context):
        assert ctx.guild is not None
        if ctx.invoked_subcommand is None:
            view = GuildConfigurationView(self.client, ctx)
            await view.send()

    @configure_command.command( # type: ignore
        name='add-xp-exempt-role',
        brief='Exempts the specified role from earning XP.',
        usage='<role>',
        category=AdministrationCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @commands.has_permissions(manage_roles=True) # type: ignore
    @commands.guild_only() # type: ignore
    async def add_xp_exempt_role_command(self, ctx: Context, role: Role):
        assert ctx.guild is not None
        config = await self.client.fetch_guild_configuration(ctx.guild.id)

        if role.id in config.xp_exempt_roles:
            raise BadArgument("Specified role is already exempt from earning XP.")
        
        await config.add_xp_exempt_role_id(role.id)
        await ctx.reply(embed=SuccessEmbed(
            'Role has been exempted from earning XP successfully.'
        ))

    @configure_command.command( # type: ignore
        name='remove-xp-exempt-role',
        brief='Removes XP earning exemption from the specified role.',
        usage='<role>',
        category=AdministrationCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @commands.has_permissions(manage_roles=True) # type: ignore
    @commands.guild_only() # type: ignore
    async def remove_xp_exempt_role_command(self, ctx: Context, role: Role):
        assert ctx.guild is not None
        config = await self.client.fetch_guild_configuration(ctx.guild.id)

        if role.id not in config.xp_exempt_roles:
            raise BadArgument("Specified role is not exempt from earning XP.")
        
        await config.remove_xp_exempt_role_id(role.id)
        await ctx.reply(embed=SuccessEmbed(
            'Role has been removed from exemption list.'
        ))

    @configure_command.command( # type: ignore
        name='add-xp-exempt-channel',
        brief='Exempts the specified channel from earning XP.',
        usage='<channel>',
        category=AdministrationCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @commands.has_permissions(manage_channels=True) # type: ignore
    @commands.guild_only() # type: ignore
    async def add_xp_exempt_channel_command(self, ctx: Context, channel: TextChannel):
        assert ctx.guild is not None
        config = await self.client.fetch_guild_configuration(ctx.guild.id)

        if channel.id in config.xp_exempt_channels:
            raise BadArgument("Specified channel is already exempt from earning XP.")
        
        await config.add_xp_exempt_channel_id(channel.id)
        await ctx.reply(embed=SuccessEmbed(
            'Channel has been exempted from earning XP successfully.'
        ))

    @configure_command.command( # type: ignore
        name='remove-xp-exempt-channel',
        brief='Removes XP earning exemption from the specified channel.',
        usage='<channel>',
        category=AdministrationCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @commands.has_permissions(manage_channels=True) # type: ignore
    @commands.guild_only() # type: ignore
    async def remove_xp_exempt_channel_command(self, ctx: Context, channel: TextChannel):
        assert ctx.guild is not None
        config = await self.client.fetch_guild_configuration(ctx.guild.id)

        if channel.id not in config.xp_exempt_channels:
            raise BadArgument("Specified channel is not exempt from earning XP.")
        
        await config.remove_xp_exempt_channel_id(channel.id)
        await ctx.reply(embed=SuccessEmbed(
            'Channel has been removed from exemption list.'
        ))

    @configure_command.command( # type: ignore
        name="setup-jail-system",
        brief="Sets up server jail system automatically. Creates a jail channel, role and sets up the permissions.",
        category=AdministrationCategory
    )
    @commands.bot_has_guild_permissions(manage_roles=True, manage_channels=True, send_messages=True) # type: ignore
    @commands.has_permissions(manage_roles=True, manage_channels=True) # type: ignore
    @commands.max_concurrency(number=1, per=commands.BucketType.guild) # type: ignore
    @commands.guild_only() # type: ignore
    async def setupjail_command(self, ctx: Context):
        assert ctx.guild is not None
        # Create empty array where we will store setup log
        action_log: List[str] = []
        async with ctx.typing():

            # Check if jailed role already exists, if not, create it
            existing_jail_role = discord.utils.get(ctx.guild.roles, name="Jailed")
            if existing_jail_role is None:
                jail_role = await ctx.guild.create_role(
                    name='Jailed',
                    reason=SETUP_REASON
                )
                action_log.append(f"Created {jail_role.mention} role; you are recommended to update role position in the role list")
            else:
                jail_role = existing_jail_role
                action_log.append(f"Reused already existing {existing_jail_role.mention} role")
            
            # Store guild channels before creating a new one
            guild_channels = ctx.guild.channels

            # Do the same for jail channel
            existing_jail_channel = discord.utils.get(ctx.guild.channels, name="jail")
            if existing_jail_channel and isinstance(existing_jail_channel, TextChannel):
                jail_channel = existing_jail_channel
                action_log.append(f"Reused already existing {existing_jail_channel.mention} channel")

            # If jail text channel not found, create it
            else:
                jail_channel = await ctx.guild.create_text_channel(
                    'jail',
                    overwrites={
                        ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                        jail_role: discord.PermissionOverwrite(read_messages=True)
                    },
                    reason=SETUP_REASON
                )
                action_log.append(f"Created {jail_channel.mention} channel")

            # Update permissions
            cnt = 0
            for channel in guild_channels:
                has_overwrite = channel.overwrites_for(jail_role).read_messages is not None
                if channel.id == jail_channel.id:
                    if not channel.permissions_for(jail_role).read_messages:
                        await channel.set_permissions(jail_role, read_messages=True, reason=SETUP_REASON)
                    continue

                if not has_overwrite: # Saves on API requests, does not know if everyone can see it or not
                    await channel.set_permissions(jail_role, read_messages=False, reason=SETUP_REASON)
                    cnt += 1
            if cnt > 0:
                action_log.append(f"Set to deny read messages permission for {jail_role.mention} in {cnt} channels")

            # Acquire config and submit changes to the database
            config = await self.client.fetch_guild_configuration(ctx.guild.id)

            config.jail_role_id = jail_role.id
            config.jail_channel_id = jail_channel.id
            await config._update()

        await ctx.reply("Jail system setup complete:\n- " + '\n- '.join(action_log), allowed_mentions=AllowedMentions(roles=False))

    @commands.command( # type: ignore
        brief='Returns current server bot prefix.',
        category=UtilityCategory
    )
    @commands.bot_has_permissions(send_messages=True) # type: ignore
    @commands.guild_only() # type: ignore
    async def prefix(self, ctx: Context):
        assert ctx.guild is not None
        config = await self.client.fetch_guild_configuration(ctx.guild.id)

        prefixes = config.guild_prefixes.prefixes or self.client.prefixes
        prefix_str = '**, **'.join(prefixes)

        await ctx.reply(f"My prefixes are: **{prefix_str}**")

async def setup(client: Pidroid):
    await client.add_cog(SettingsCommands(client))
