import pytest

from pidroid.utils import (
    format_version_code,
    role_mention, user_mention, channel_mention,
    clean_inline_translations, truncate_string
)


def test_format_version_code():
    # Undefined behaviour
    assert format_version_code(1) == "1"
    assert format_version_code(12) == "12"
    # Actually defined behaviour
    assert format_version_code(248) == "1.2.48"
    assert format_version_code(2482) == "2.4.82"
    assert format_version_code(24826) == "2.48.26"
    # Undefined behaviour
    assert format_version_code(245897) == "245897"

def test_role_mention():
    ROLE_ID = 86868697123
    assert role_mention(ROLE_ID) == f"<@&{ROLE_ID}>"

def test_user_mention():
    USER_ID = 1234567890
    assert user_mention(USER_ID) == f"<@{USER_ID}>"

def test_channel_mention():
    CHANNEL_ID = 1234567890
    assert channel_mention(CHANNEL_ID) == f"<#{CHANNEL_ID}>"

def test_clean_inline_translation():
    assert clean_inline_translations("Oh, the sun's out. When did that happen?") == "Oh, the sun's out. When did that happen?"
    assert clean_inline_translations("[lt] Va cia tai ugnis") == "[lt] Va cia tai ugnis"
    assert clean_inline_translations("Now this is fire [lt]Va cia tai ugnis") == "Now this is fire "
    assert clean_inline_translations("[en]Now this is fire [lt]Va cia tai ugnis") == "[en]Now this is fire [lt]Va cia tai ugnis"

def test_truncate_string():
    assert truncate_string("Long long maaaaaaaaaan", replace_value="...", max_length=10) == "Long lo..."
    assert truncate_string("Long long maaaaaaaaaan", replace_value="..", max_length=10) == "Long lon.."
    assert truncate_string("Long long maaaaaaaaaan", replace_value="<removed>", max_length=10) == "L<removed>"
    assert truncate_string("Long long maaaaaaaaaan", replace_value="<removed>", max_length=9) == "<removed>"
    
    assert    truncate_string("Long long maaaaaaaaaan", replace_value="<removed>", max_length=8) == "Long lon"

    with pytest.raises(ValueError):
        truncate_string("Long long maaaaaaaaaan", replace_value="<removed>", max_length=0)

    assert truncate_string("", replace_value="<removed>", max_length=1) == ""
    assert truncate_string("DSA", replace_value="<removed>", max_length=1) == "D"
