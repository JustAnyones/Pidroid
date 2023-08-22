from enum import Enum

class EventType(Enum):
    # Punishment related
    punishment_issue = 1
    punishment_revoke = 2

    # Tag related
    tag_create = 3
    tag_update = 4
    tag_delete = 5

    # Guild config related
    update_guild_configuration = 6

class EventName(Enum):

    tag_create        = "tag_create"
    tag_edit          = "tag_edit"
    tag_claim         = "tag_claim"
    tag_author_update = "tag_author_update"
    tag_transfer      = "tag_transfer"
    tag_update        = "tag_update"
    tag_delete        = "tag_delete"
