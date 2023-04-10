import re

# Compile patters upon load for performance
INLINE_TRANSLATION_PATTERN = re.compile(r'\[.*].*', flags=re.DOTALL)

def format_version_code(version_code: int) -> str:
    """Converts version code of TheoTown to a version name string. Returns original input string on failure."""
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
