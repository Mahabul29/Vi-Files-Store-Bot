from pyrogram import filters

# (bot_id, user_id) -> {"mode": "...", ...}  pending input state
STATE = {}


def in_state(prefix: str):
    """Filter: user has a pending input whose mode starts with `prefix` ('' = any)."""

    async def _f(_, client, m):
        if not m.from_user:
            return False
        s = STATE.get((client.bot_id, m.from_user.id))
        return bool(s) and s["mode"].startswith(prefix)

    return filters.create(_f, name=f"InState_{prefix or 'any'}")
