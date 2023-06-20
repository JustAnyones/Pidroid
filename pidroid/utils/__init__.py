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
