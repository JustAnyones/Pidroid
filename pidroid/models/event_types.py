from enum import Enum

class EventType(Enum):
    # Punishment related
    punishment_issue = 1
    punishment_revoke = 2

    # Tag related
    create_tag = 3
    update_tag = 4
    delete_tag = 5

    # Guild config related
    update_guild_configuration = 6
