import enum

class MenuStage(enum.Enum):
    """Represents the current stage of the ModmenuView."""
    TYPE_SELECTION = 0
    CONFIRMATION = 3
    CANCELLED = 4
    TIMED_OUT = 5
    FINISHED = 6

    EDIT_REASON = 1
    EDIT_DATE_EXPIRE = 2
    EDIT_DELETE_MESSAGE_DAYS = 7
