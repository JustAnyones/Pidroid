def normalize_permission_name(name: str) -> str:
    """Returns a normalized permission name."""
    return (name
            .replace('_', ' ')
            .replace('guild', 'server')
            .title()
            .replace('Tts', 'TTS')
        )