from typing import Optional

from pidroid.models.guild_configuration import GuildConfiguration

class GuildInformation:

    """This object represents Pidroid's configurable guild information.
    
    This also exposes useful methods."""

    def __init__(self, conf: GuildConfiguration) -> None:
        self.__api = conf.api
        self.__guild_config = conf
        self.__guild_id = conf.guild_id
        
        self.__logging_enabled = False # TODO: remove after debugging

    @property
    def xp_system_active(self) -> bool:
        """Returns true if XP system is currently active in the guild."""
        return self.__guild_config.xp_system_active

    @property
    def level_rewards_stacked(self) -> bool:
        """Returns true if level rewards obtained from the level system should be stacked."""
        return self.__guild_config.stack_level_rewards
    
    @property
    def logging_channel_id(self) -> Optional[int]:
        """Returns the ID of the logging channel if available."""
        return self.__guild_config.log_channel
    
    @property
    def logging_active(self) -> bool:
        """Returns true if logging system is enabled for the server."""
        return self.__logging_enabled

    async def fetch_all_level_rewards(self):
        """Returns a list of all level rewards in the guild."""
        return await self.__api.fetch_all_guild_level_rewards(self.__guild_id)
    
    async def fetch_member_level(self, member_id: int):
        """Returns member level object."""
        return await self.__api.fetch_user_level_info(self.__guild_id, member_id)

    async def fetch_all_member_levels(self):
        """Returns a list of member level information for every member in the guild."""
        return await self.__api.fetch_guild_level_infos(self.__guild_id)