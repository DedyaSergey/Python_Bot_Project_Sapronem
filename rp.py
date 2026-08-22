RP_COMMANDS = {
    "обнять": ("🤗", "обнял(а)"),
    "поцеловать": ("💋", "поцеловал(а)"),
    "ударить": ("👊", "ударил(а)"),
    "укусить": ("🦷", "укусил(а)"),
    "похвалить": ("🤝", "похвалил(а)"),
    "дать леща": ("🐟", "отвесил(а) леща")
}

def check_rp(text: str):
    if not text:
        return None
    text_lower = text.lower().strip()
    if text_lower in RP_COMMANDS:
        return RP_COMMANDS[text_lower]
    return None
