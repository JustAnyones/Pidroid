import enum

class MenuStage(enum.Enum):
    """Represents the current stage of the ModmenuView."""
    TYPE_SELECTION = 0
    REASON_EDIT = 1
    EXPIRES_EDIT = 2
    CONFIRMATION = 3
    CANCELLED = 4
    TIMED_OUT = 5
    FINISHED = 6
