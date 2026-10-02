async def get_message_id(client, message) -> int:
    origin = getattr(message, "forward_origin", None)
    fchat = getattr(message, "forward_from_chat", None)
    fmid = getattr(message, "forward_from_message_id", None)
    if origin is not None:
        fchat = getattr(origin, "chat", None) or fchat
        fmid = getattr(origin, "message_id", None) or fmid
    if fchat:
        return fmid if fchat.id == CHANNEL_ID else 0
    if origin is not None or getattr(message, "forward_sender_name", None):
        return 0
    if message.text:
        m = re.match(r"https://t\.me/(?:c/)?([^/]+)/(\d+)", message.text.strip())
        if not m:
            return 0
        chan, msg_id = m.group(1), int(m.group(2))
        if chan.isdigit():
            return msg_id if f"-100{chan}" == str(CHANNEL_ID) else 0
        uname = getattr(client.db_channel, "username", None)
        return msg_id if uname and chan.lower() == uname.lower() else 0
    return 0
