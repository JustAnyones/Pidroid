import ast
import asyncio
import inspect
import textwrap
import discord
import re

from dataclasses import dataclass
from functools import partial
from typing import List, Optional, Union

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

async def try_message_user(
    user: Union[discord.Member, discord.User],
    *,
    content: Optional[str] = None,
    embed: Optional[discord.Embed] = None
) -> Optional[discord.Message]:
    """Tries to send a message to the user in direct messages. Returns bool whether message was delivered successfully."""
    try:
        if embed:
            message = await user.send(content=content, embed=embed)
        else:
            message = await user.send(content=content)
        return message
    except Exception: # nosec
        return None
    
async def run_in_executor(func, **kwargs):
    """Runs the specified function in executor.
    
    Can be used to run blocking code."""
    return await asyncio.get_event_loop().run_in_executor(
        None,
        partial(func, **kwargs)
    )

@dataclass
class Decorator:
    func: List[str]
    keywords: List[tuple]

    def is_a_check(self) -> bool:
        """Returns true if this decorator is a check."""

        if self.func[-1] in [
            "command", "group",
            "hybrid_command", "hybrid_group",
            "describe", "cooldown", "max_concurrency"
        ]:
            return False

        return True
    
    @property
    def requirement_text(self) -> str:
        
        if self.func[-1] == "is_nsfw":
            return "Inside a NSFW channel"
        
        if self.func[-1] == "is_theotown_developer":
            return "TheoTown developer"
        
        if self.func[-1] == "guild_only":
            return "Inside a server"
        
        if self.func[-1] == "can_purge":
            return "Can purge"

        if self.func[-1] == "client_is_pidroid":
            return "I am Pidroid"
        
        if self.func[-1] == "bot_has_permissions" or self.func[-1] == "bot_has_guild_permissions":
            builder = "Bot permissions:\n"
            for name, value in self.keywords:
                builder += f" - {name}: {value}\n"
            return builder.strip()
        
        if self.func[-1] == "has_permissions" or self.func[-1] == "has_guild_permissions":
            builder = "Your permissions:\n"
            for name, value in self.keywords:
                builder += f" - {name}: {value}\n"
            return builder.strip()

        if self.keywords:
            return ', '.join(
                [f'{keyword[0]}: {keyword[1]}' for keyword in self.keywords]
            )
        
        return '.'.join(self.func)

def _parse_attribute(
    attribute: ast.Attribute,
    *,
    attributes: Optional[List[str]] = None
):

    # If list was not passed, create it
    if attributes is None:
        attributes = []

    # If it's value
    if isinstance(attribute.value, ast.Name):
        attributes.append(attribute.value.id)
        attributes.append(attribute.attr)

    # If it's another attribute
    elif isinstance(attribute.value, ast.Attribute):
        _parse_attribute(attribute.value, attributes=attributes)
        attributes.append(attribute.attr)

    return attributes

def _parse_call_name(call: ast.Call) -> List[str]:
    if isinstance(call.func, ast.Attribute):
        return _parse_attribute(call.func)

    elif isinstance(call.func, ast.Name):
        return [call.func.id]

    raise ValueError("Unknown call func attribute")


def get_function_decorators(func) -> List[Decorator]:
    # Get the source code of the function
    source_code = inspect.getsource(func)

    # Remove identation
    dedented_code = textwrap.dedent(source_code)

    # Parse the source code into an AST
    tree = ast.parse(dedented_code)

    # Extract decorator information from the AST
    decorators: List[ast.Call] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator_node in node.decorator_list:
                assert isinstance(decorator_node, ast.Call)
                decorators.append(decorator_node)
                print(f"Decorator:", ast.dump(decorator_node))

    print()
    parsed = []
    for dec in decorators:

        call_name = _parse_call_name(dec)

        # Parse every keyword
        keywords: List[tuple] = []
        for keyword in dec.keywords:
            assert isinstance(keyword, ast.keyword)


            value = None
            if isinstance(keyword.value, ast.Constant):
                value = keyword.value.value

            elif isinstance(keyword.value, ast.Name):
                value = keyword.value.id

            elif isinstance(keyword.value, ast.List):
                value = []
                for elem in keyword.value.elts:
                    print(elem)

            else:
                print(keyword.__dict__)
                print(keyword.value)
                print(dir(keyword.value))
                print(keyword.value.__dict__)

            keywords.append((
                keyword.arg, value
            ))

        parsed.append(
            Decorator(
                func=call_name,
                keywords=keywords
            )
        )
    return parsed
