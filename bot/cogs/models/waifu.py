from typing import Any, TYPE_CHECKING, Optional


def reformat_value(value) -> Optional[Any]:
    """Fixes any API response values which are empty strings or an integer of 0 to None.
    Otherwise, returns the original value."""
    if value == 0 or value == "":
        return None
    return value


class Birthday:
    """This class represents birthday of a waifu."""

    if TYPE_CHECKING:
        year: Optional[str]
        month: Optional[str]
        day: Optional[int]

    def __init__(self, year, month, day) -> None:
        self.year = reformat_value(year)
        self.month = reformat_value(month)
        self.day = reformat_value(day)

class Waifu:
    """This class represents Mywaifulist Waifu."""

    if TYPE_CHECKING:
        id: int
        slug: str
        url: str

        name: str
        original_name: Optional[str]
        romaji_name: Optional[str]
        description: Optional[str]
        display_picture: str

        is_husbando: bool
        is_nsfw: bool

        age: Optional[int]
        birthday: Birthday
        appearance: dict

        series: Optional[list]
        appearances: Optional[list]
        tags: list

    def __init__(self, dictionary: dict) -> None:
        self.id = dictionary["id"]
        self.slug = dictionary["slug"]
        self.url = dictionary["url"]

        self.name = dictionary["name"]
        self.original_name = reformat_value(dictionary["original_name"])
        self.romaji_name = reformat_value(dictionary["romaji_name"])
        self.description = reformat_value(dictionary["description"])
        self.display_picture = dictionary["display_picture"]

        self.is_husbando = dictionary["husbando"]
        self.is_nsfw = dictionary["nsfw"]

        self.age = reformat_value(dictionary["age"])
        self.birthday = Birthday(
            dictionary["birthday_year"],
            dictionary["birthday_month"],
            dictionary["birthday_day"]
        )

        # TODO: add specific class
        self.appearance = {
            "weight": dictionary["weight"],
            "height": dictionary["height"],
            "bust": dictionary["bust"],
            "hip": dictionary["hip"],
            "waist": dictionary["waist"],
            "blood_type": dictionary["blood_type"],
            "origin": dictionary["origin"],
        }

        self.series = dictionary["series"] # TODO: add specific class
        self.appearances = dictionary["appearances"] # TODO: add specific class
        self.tags = dictionary["tags"] # TODO: add specific class
