import discord
import re

from typing import Optional, Union

# Compile patters upon load for performance
INLINE_TRANSLATION_PATTERN = re.compile(r'\[.*].*', flags=re.DOTALL)

def normalize_permission_name(name: str) -> str:
    """Returns a normalized permission name."""
    return (name
            .replace('_', ' ')
            .replace('guild', 'server')
            .title()
            .replace('Tts', 'TTS')
        )

def role_mention(role_id: int) -> str:
    """Returns role mention string for the specified role ID.
    
    Acquiring an entire role object just to call mention property might not always
    be a good idea."""
    return f"<@&{role_id}>"

def user_mention(user_id: int) -> str:
    """Returns user mention string for the specified user ID.
    
    Acquiring an entire User or Member object just to call mention property might not always
    be a good idea."""
    return f"<@{user_id}>"

def channel_mention(channel_id: int) -> str:
    """Returns channel mention string for the specified user ID.
    
    Acquiring an entire Channel object just to call mention property might not always
    be a good idea."""
    return f"<#{channel_id}>"

def format_version_code(version_code: int) -> str:
    """Converts version code of TheoTown to a version name string. Returns original input as string on failure."""
    string = str(version_code)
    length = len(string)
    if length == 3:
        return '1.' + string[0] + '.' + string[1:]
    if length == 4:
        return string[0] + '.' + string[1:2] + '.' + string[2:]
    if length == 5:
        return string[0] + '.' + string[1:3] + '.' + string[3:]
    return string

def clean_inline_translations(string: str) -> str:
    """Attempts to remove inline translations from a string. Returns original input string on failure."""
    return_string = re.sub(INLINE_TRANSLATION_PATTERN, '', string)
    if len(return_string) == 0:
        return string
    return return_string

def truncate_string(string: str, max_length: int = 2048, replace_value: str = '...') -> str:
    """Shortens string to a specified length."""
    if len(string) > max_length:
        return string[:max_length - len(replace_value)] + replace_value
    return string

async def try_message_user(user: Union[discord.Member, discord.User], embed: discord.Embed) -> Optional[discord.Message]:
    """Tries to send a embed to the user in direct messages. Returns bool whether message was delivered successfully."""
    try:
        message = await user.send(embed=embed)
        return message
    except Exception: # nosec
        return None