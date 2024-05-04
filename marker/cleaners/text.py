import re


def cleanup_text(full_text):
    full_text = re.sub(r'\n{3,}', '\n\n', full_text)
    full_text = re.sub(r'(\n\s){3,}', '\n\n', full_text)
    full_text = full_text.replace('\xa0', ' ') # Replace non-breaking spaces
    return full_text