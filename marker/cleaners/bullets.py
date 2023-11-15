import re


def replace_bullets(text):
    # Replace bullet characters with a -
    bullet_pattern = r"(^|[\n ])[•●○■▪▫–—]( )"
    replaced_string = re.sub(bullet_pattern, r"\1-\2", text)
    return replaced_string
