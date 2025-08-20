from __future__ import annotations

import discord
import logging
import re

from collections.abc import Sequence
from contextlib import suppress
from discord import AllowedMentions, Colour, Interaction, NotFound, TextChannel, Role
from discord.ext import commands
from discord.ext.commands.context import Context
from discord.ext.commands.errors import BadArgument
from typing import Generic, TypeVar, override

from pidroid.client import Pidroid
from pidroid.models.categories import AdministrationCategory, BotCategory
from pidroid.models.guild_configuration import GuildConfiguration
from pidroid.modules.core.ui.opt.impl import BooleanOptionImpl, ChannelOptionImpl, FloatOptionImpl, RoleOptionImpl, StringButton, StringOptionImpl
from pidroid.modules.core.ui.opt.control import BooleanControl, ChannelControl, FloatControl, Control, ReadonlyControl, RoleControl, StringControl
from pidroid.utils.embeds import PidroidEmbed, SuccessEmbed

logger = logging.getLogger('Pidroid')

SETUP_REASON = "Server jail system setup"

# https://www.geeksforgeeks.org/check-if-an-url-is-valid-or-not-using-regular-expression/
URL_REGEX = re.compile((
    "((http|https)://)(www.)?"
    "[a-zA-Z0-9@:%._\\+~#?&//=]"
    "{2,256}\\.[a-z]"
    "{2,6}\\b([-a-zA-Z0-9@:%"
    "._\\+~#?&//=]*)"
))

FORBIDDEN_PREFIXES = [',', '\\', '/']

RV = TypeVar('RV')  # Return value of the button callback
V = TypeVar('V', bound='discord.ui.view.BaseView', covariant=True)

class NewChangePrefixesButton(StringButton[V, list[str]]):

    @override
    async def handle_value(self, value: str) -> tuple[list[str], str | None]:
        value, err = self.parse_string_value(value)
        if err:
            return [], err
        assert value

        if value == ",":
            return [], "Comma is used as a separator, please use another character."
        split_values = value.split(',')
        
        # Limit prefixes
        if len(split_values) > 5:
            return [], "You can only define up to 5 prefixes."
        
        cleaned_prefixes: list[str] = []
        for value in split_values:
            stripped = value.strip()
            if stripped == "":
                continue
            if stripped in FORBIDDEN_PREFIXES:
                return [], f"'{stripped}' cannot be used as a prefix."
            if len(stripped) > 5:
                return [], f"For best user experience, please keep prefix '{stripped}' below 5 characters."
            cleaned_prefixes.append(stripped)
            
        if len(cleaned_prefixes) == 0:
            return [], "You did not specify any valid prefixes."

        return cleaned_prefixes, None

class NewChangeBanAppealUrlButton(StringButton[V, str]):

    @override
    async def handle_value(self, value: str) -> tuple[str, str | None]:
        value, err = self.parse_string_value(value)
        if err:
            return "", err
        
        # Empty values are allowed as it's used to unset it
        if value == '':
            return value, None

        # If URL is valid
        if re.search(URL_REGEX, value):
            return value, None
        
        # If URL is not valid
        return "", "The URL that you have provided is not a valid URL."


class Submenu(Generic[V]):

    def __init__(self, *, name: str, description: str, view: V, settings: Sequence[Control[V]]) -> None:
        self.__name = name
        self.__description = description
        self.view: V = view
        self.__settings = settings

    @property
    def embed(self) -> PidroidEmbed:
        embed = PidroidEmbed(title=self.__name, description=self.__description)
        assert embed.description
        for setting in self.__settings:
            if setting.description:
                embed.description += f"\n- {setting.name}: {setting.description}"
            embed.add_field(name=setting.name, value=setting.value_as_str)
        embed.set_footer(text="Any change that you make here will be applied instantly.")
        return embed
    
    @property
    def items(self) -> list[discord.ui.Item[V]]:
        return [
            setting.as_item()
            for setting in self.__settings
            if not isinstance(setting, ReadonlyControl)
        ]

class SubmenuSelect(discord.ui.Select['GuildConfigurationView']):

    def __init__(self) -> None:
        super().__init__(placeholder="Select submenu", options=SUBMENU_OPTIONS)

    @override
    async def callback(self, interaction: Interaction):
        assert self.view is not None
        success = await self.view.change_menu(interaction, self.values[0])
        if not success:
            await interaction.response.send_message("You selected a menu that does not exist!", ephemeral=True)

class CloseButton(discord.ui.Button['GuildConfigurationView']):

    def __init__(self):
        super().__init__(style=discord.ButtonStyle.red, label="Close")

    @override
    async def callback(self, interaction: Interaction):
        assert self.view is not None
        await self.view.close_interface(interaction)


class GeneralSubmenu(Submenu['GuildConfigurationView']):

    def __init__(self, *, view: GuildConfigurationView, configuration: GuildConfiguration) -> None:
        prefixes = configuration.prefixes or configuration.api.client.prefixes

        async def change_prefixes_callback(interaction: Interaction, prefixes: list[str]):
            await configuration.edit(prefixes=prefixes)
            await view.refresh_menu(interaction)

        async def toggle_tag_management_callback(interaction: Interaction):
            await configuration.edit(public_tags=not configuration.public_tags)
            await view.refresh_menu(interaction)

        settings=[
            StringControl(
                name="Prefixes",
                value=', '.join(prefixes),
                impl=StringOptionImpl[GuildConfigurationView, list[str]](
                    cls=NewChangePrefixesButton,
                    label="Change prefixes",
                    modal_title="Change command prefixes",
                    placeholder="Provide a comma-separated list of prefixes. E.g. !, ?, P, TT",
                ),
                callback=change_prefixes_callback,  
            ),
            BooleanControl(
                name="Everyone can manage tags",
                value=configuration.public_tags,
                impl=BooleanOptionImpl[GuildConfigurationView](
                    label_true="Allow everyone to manage tags",
                    label_false="Don't allow everyone to manage tags"
                ),
                callback=toggle_tag_management_callback,
            ),
        ]
        super().__init__(
            name="General settings",
            description="This submenu contains general settings related to the functioning of Pidroid within this server.",
            view=view,
            settings=settings
        )

class ModerationSubmenu(Submenu['GuildConfigurationView']):

    def __init__(self, *, view: GuildConfigurationView, configuration: GuildConfiguration) -> None:
        assert configuration.guild is not None

        async def change_jail_role_callback(interaction: Interaction, role_ids: list[int]):
            await configuration.edit(jail_role_id=role_ids[0] if role_ids else None)
            await view.refresh_menu(interaction)

        async def change_jail_channel_callback(interaction: Interaction, channel_ids: list[int]):
            await configuration.edit(jail_channel_id=channel_ids[0] if channel_ids else None)
            await view.refresh_menu(interaction)

        async def change_allow_to_punish_moderators_callback(interaction: Interaction):
            await configuration.edit(allow_moderator_punishing=not configuration.allow_to_punish_moderators)
            await view.refresh_menu(interaction)

        async def change_ban_appeal_url_callback(interaction: Interaction, appeal_url: str):
            await configuration.edit(appeal_url=appeal_url)
            await view.refresh_menu(interaction)

        settings=[
            RoleControl(
                name="Jail role",
                value=configuration.jail_role_id,
                guild=configuration.guild,
                impl=RoleOptionImpl[GuildConfigurationView](
                    placeholder="Change jail role",
                ),
                callback=change_jail_role_callback,
            ),
            ChannelControl(
                name="Jail channel",
                value=configuration.jail_channel_id,
                guild=configuration.guild,
                impl=ChannelOptionImpl[GuildConfigurationView](
                    channel_types=[discord.ChannelType.text],
                    placeholder="Change jail channel",
                ),
                callback=change_jail_channel_callback,
            ),
            BooleanControl(
                name="Allow to punish moderators",
                value=configuration.allow_to_punish_moderators,
                impl=BooleanOptionImpl[GuildConfigurationView](
                    label_true="Allow to punish moderators",
                    label_false="Don't allow to punish moderators",
                ),
                callback=change_allow_to_punish_moderators_callback,
            ),
            StringControl(
                name="Ban appeal URL",
                value=configuration.appeal_url or "Not set",
                impl=StringOptionImpl[GuildConfigurationView, str](
                    cls=NewChangeBanAppealUrlButton,
                    label="Change ban appeal URL",
                    modal_title="Change ban appeal URL",
                    placeholder="Provide a valid URL or nothing to remove it.",
                    required=False
                ),
                callback=change_ban_appeal_url_callback,
            )
        ]
        super().__init__(
            name="Moderation settings",
            description="This submenu contains settings related to the Pidroid's punishment and moderation system.",
            view=view,
            settings=settings
        )
        
class LevelingSubmenu(Submenu['GuildConfigurationView']):

    def __init__(self, *, view: GuildConfigurationView, configuration: GuildConfiguration) -> None:
        assert configuration.guild is not None
        # Store xp exempt channel mentions
        channels: list[str] = []
        for c_id in configuration.xp_exempt_channels:
            chan = configuration.guild.get_channel(c_id)
            if chan:
                channels.append(chan.mention)
        # Store xp exempt role mentions
        roles: list[str] = []
        for r_id in configuration.xp_exempt_roles:
            role = configuration.guild.get_role(r_id)
            if role:
                roles.append(role.mention)

        async def toggle_leveling_system_callback(interaction: Interaction):
            await configuration.edit(
                xp_system_active=not configuration.xp_system_active
            )
            await view.refresh_menu(interaction)

        async def change_xp_multiplier_callback(interaction: Interaction, multiplier: float):
            await configuration.edit(xp_multiplier=multiplier)
            await view.refresh_menu(interaction)

        async def toggle_reward_stacking_callback(interaction: Interaction):
            await configuration.edit(
                stack_level_rewards=not configuration.level_rewards_stacked
            )
            await view.refresh_menu(interaction)
        
        settings=[
            BooleanControl(
                name="Leveling system active",
                value=configuration.xp_system_active,
                impl=BooleanOptionImpl[GuildConfigurationView](
                    label_true="Enable leveling system",
                    label_false="Disable leveling system",
                ),
                callback=toggle_leveling_system_callback,
            ),
            FloatControl(
                name="XP multiplier",
                value=configuration.xp_multiplier,
                impl=FloatOptionImpl[GuildConfigurationView](
                    label="Change XP multiplier",
                    modal_title="Change XP multiplier",
                    placeholder="Provide a floating point value between 0 and 2.",
                    min_value=0,
                    max_value=2
                ),
                callback=change_xp_multiplier_callback,    
            ),
            ReadonlyControl[GuildConfigurationView](
                name="XP exempt channels",
                description="You can manage this setting with a subcommand.",
                value=','.join(channels) if channels else None
            ),
            ReadonlyControl[GuildConfigurationView](
                name="XP exempt roles",
                description="You can manage this setting with a subcommand.",
                value=','.join(roles) if roles else None
            ),
            BooleanControl(
                name="XP rewards stacked",
                value=configuration.level_rewards_stacked,
                impl=BooleanOptionImpl[GuildConfigurationView](
                    label_true="Stack level rewards",
                    label_false="Don't stack level rewards",
                ),
                callback=toggle_reward_stacking_callback,
            ),
        ]
        super().__init__(
            name="Leveling settings",
            description="This submenu contains settings related to Pidroid's XP and level rewards system.",
            view=view,
            settings=settings
        )

class SuggestionSubmenu(Submenu['GuildConfigurationView']):

    def __init__(self, *, view: GuildConfigurationView, configuration: GuildConfiguration) -> None:
        assert configuration.guild is not None

        async def toggle_suggestion_callback(interaction: Interaction):
            await configuration.edit(
                suggestion_system_active=not configuration.suggestion_system_active
            )
            await view.refresh_menu(interaction)

        async def toggle_suggestion_threads_callback(interaction: Interaction):
            await configuration.edit(
                suggestion_threads_enabled=not configuration.suggestion_threads_enabled
            )
            await view.refresh_menu(interaction)

        async def change_suggestion_channel_callback(interaction: Interaction, channel_ids: list[int]):
            await configuration.edit(suggestion_channel_id=channel_ids[0] if channel_ids else None)
            await view.refresh_menu(interaction)

        settings=[
            BooleanControl(
                name="Suggestion system active",
                value=configuration.suggestion_system_active,
                impl=BooleanOptionImpl[GuildConfigurationView](
                    label_true="Enable suggestion system",
                    label_false="Disable suggestion system",
                ),
                callback=toggle_suggestion_callback,
            ),
            BooleanControl(
                name="Create threads for suggestions",
                value=configuration.suggestion_threads_enabled,
                impl=BooleanOptionImpl[GuildConfigurationView](
                    label_true="Enable threads for suggestions",
                    label_false="Disable threads for suggestions",
                ),
                callback=toggle_suggestion_threads_callback,
            ),
            ChannelControl(
                name="Suggestion channel",
                value=configuration.suggestions_channel_id,
                guild=configuration.guild,
                impl=ChannelOptionImpl[GuildConfigurationView](
                    channel_types=[discord.ChannelType.text],
                    placeholder="Change suggestion channel",
                ),
                callback=change_suggestion_channel_callback,
            ),
        ]
        super().__init__(
            name="Suggestion settings",
            description="This submenu contains settings related to Pidroid's suggestion system.",
            view=view,
            settings=settings
        )

SUBMENUS = {
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

    def __init__(self, client: Pidroid, ctx: Context[Pidroid], *, timeout: float = 600):
        super().__init__(timeout=timeout)
        self.__client = client
        self.__ctx = ctx
        self.__embed = PidroidEmbed()
        self.__current_submenu: str | None = None
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
        
        menu = submenu(view=self, configuration=config)

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

    async def timeout_interface(self, interaction: Interaction | None) -> None:
        """Called to clean up when the interaction or interface timed out."""
        self.__embed.set_footer(text="Settings menu has timed out")
        self.__embed.colour = Colour.red()
        await self.finish_interface(interaction)

    async def error_interface(self, interaction: Interaction | None) -> None:
        """Called to clean up when an error is encountered."""
        self.__embed.set_footer(text="Settings menu has encountered an unexpected error")
        self.__embed.colour = Colour.red()
        await self.finish_interface(interaction)

    async def finish_interface(
        self,
        interaction: Interaction | None,
        embed: PidroidEmbed | None = None
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

    async def _update_view(self, interaction: Interaction | None) -> None:
        """Updates the original interaction response message.
        
        If interaction object is not provided, then the message itself will be edited."""
        if interaction is None:
            with suppress(NotFound):
                await self.__message.edit(embed=self.__embed, view=self)
        else:
            await interaction.response.edit_message(embed=self.__embed, view=self)

    """Event listeners"""

    @override
    async def on_timeout(self) -> None:
        """Called when view times out."""
        await self.timeout_interface(None)

    @override
    async def on_error(self, interaction: Interaction, error: Exception, item: discord.ui.Item[V]) -> None:
        """Called when view catches an error."""
        logger.exception(error)
        logger.error(f"The above exception is caused by {str(item)} item")
        if interaction.response.is_done():
            await interaction.followup.send('An unknown error occurred, sorry', ephemeral=True)
        else:
            await interaction.response.send_message('An unknown error occurred, sorry', ephemeral=True)

        await self.error_interface(None)

    @override
    async def interaction_check(self, interaction: Interaction) -> bool:
        """Ensure that the interaction is called by the message author."""
        if interaction.user and interaction.user.id == self.__ctx.author.id:
            return True
        await interaction.response.send_message('This menu cannot be controlled by you!', ephemeral=True)
        return False

class SettingCommandCog(commands.Cog):
    """This class implements cog which contains administrator commands for Pidroid configuration management."""

    def __init__(self, client: Pidroid):
        super().__init__()
        self.client = client

    @commands.hybrid_group(
        name="configure",
        brief="Allows to manage server bot configuration.",
        category=AdministrationCategory,
        invoke_without_command=True,
        fallback="menu"
    )
    @commands.bot_has_guild_permissions(send_messages=True)
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def configure_command(self, ctx: Context[Pidroid]):
        assert ctx.guild is not None
        if ctx.invoked_subcommand is None:
            view = GuildConfigurationView(self.client, ctx)
            await view.send()

    @configure_command.command(
        name='add-xp-exempt-role',
        brief='Exempts the specified role from earning XP.',
        usage='<role>',
        category=AdministrationCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.has_permissions(manage_roles=True)
    @commands.guild_only()
    async def add_xp_exempt_role_command(self, ctx: Context[Pidroid], role: Role):
        assert ctx.guild is not None
        config = await self.client.fetch_guild_configuration(ctx.guild.id)

        if role.id in config.xp_exempt_roles:
            raise BadArgument("Specified role is already exempt from earning XP.")
        
        await config.add_xp_exempt_role_id(role.id)
        return await ctx.reply(embed=SuccessEmbed(
            'Role has been exempted from earning XP successfully.'
        ))

    @configure_command.command(
        name='remove-xp-exempt-role',
        brief='Removes XP earning exemption from the specified role.',
        usage='<role>',
        category=AdministrationCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.has_permissions(manage_roles=True)
    @commands.guild_only()
    async def remove_xp_exempt_role_command(self, ctx: Context[Pidroid], role: Role):
        assert ctx.guild is not None
        config = await self.client.fetch_guild_configuration(ctx.guild.id)

        if role.id not in config.xp_exempt_roles:
            raise BadArgument("Specified role is not exempt from earning XP.")
        
        await config.remove_xp_exempt_role_id(role.id)
        return await ctx.reply(embed=SuccessEmbed(
            'Role has been removed from exemption list.'
        ))

    @configure_command.command(
        name='add-xp-exempt-channel',
        brief='Exempts the specified channel from earning XP.',
        usage='<channel>',
        category=AdministrationCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    async def add_xp_exempt_channel_command(self, ctx: Context[Pidroid], channel: TextChannel):
        assert ctx.guild is not None
        config = await self.client.fetch_guild_configuration(ctx.guild.id)

        if channel.id in config.xp_exempt_channels:
            raise BadArgument("Specified channel is already exempt from earning XP.")
        
        await config.add_xp_exempt_channel_id(channel.id)
        return await ctx.reply(embed=SuccessEmbed(
            'Channel has been exempted from earning XP successfully.'
        ))

    @configure_command.command(
        name='remove-xp-exempt-channel',
        brief='Removes XP earning exemption from the specified channel.',
        usage='<channel>',
        category=AdministrationCategory
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    async def remove_xp_exempt_channel_command(self, ctx: Context[Pidroid], channel: TextChannel):
        assert ctx.guild is not None
        config = await self.client.fetch_guild_configuration(ctx.guild.id)

        if channel.id not in config.xp_exempt_channels:
            raise BadArgument("Specified channel is not exempt from earning XP.")
        
        await config.remove_xp_exempt_channel_id(channel.id)
        return await ctx.reply(embed=SuccessEmbed(
            'Channel has been removed from exemption list.'
        ))

    @configure_command.command(
        name="setup-jail-system",
        brief="Sets up server jail system automatically. Creates a jail channel, role and sets up the permissions.",
        category=AdministrationCategory
    )
    @commands.bot_has_guild_permissions(manage_roles=True, manage_channels=True, send_messages=True)
    @commands.has_permissions(manage_roles=True, manage_channels=True)
    @commands.max_concurrency(number=1, per=commands.BucketType.guild)
    @commands.guild_only()
    async def setupjail_command(self, ctx: Context[Pidroid]):
        assert ctx.guild is not None
        # Create empty array where we will store setup log
        action_log: list[str] = []
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
            await config.edit(
                jail_channel_id=jail_channel.id,
                jail_role_id=jail_role.id
            )

        return await ctx.reply("Jail system setup complete:\n- " + '\n- '.join(action_log), allowed_mentions=AllowedMentions(roles=False))

    @commands.command(
        brief='Returns current server bot prefix.',
        category=BotCategory,
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    async def prefix(self, ctx: Context[Pidroid]):
        assert ctx.guild is not None
        config = await self.client.fetch_guild_configuration(ctx.guild.id)

        prefixes = config.prefixes or self.client.prefixes
        prefix_str = '**, **'.join(prefixes)

        return await ctx.reply(f"My prefixes are: **{prefix_str}** and can be changed via `{prefixes[0]}configure` command.")

async def setup(client: Pidroid):
    await client.add_cog(SettingCommandCog(client))
