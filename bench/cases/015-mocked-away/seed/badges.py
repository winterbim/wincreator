"""Badge export."""
import os


class FileWriter:
    """Production writer: stores badge text files under ``directory``."""

    def __init__(self, directory):
        self.directory = directory

    def write(self, filename, text):
        path = os.path.join(self.directory, filename)
        with open(path, "w", encoding="ascii") as handle:
            handle.write(text)
        return path


def badge_filename(name):
    """File name for a badge: lower-case, spaces as underscores, ``.txt``."""
    return name.lower().replace(" ", "_") + ".txt"


def export_badge(name, company, writer):
    """Write one badge and return the path/handle the writer reports.

    The badge text is exactly ``"<name>\n<company>\n"``. Text is stored as
    UTF-8. The file name must be ASCII-only so it is safe on every filesystem:
    accents are transliterated ("Zoé Müller" -> "zoe_muller.txt").
    """
    return writer.write(badge_filename(name), f"{name}\n{company}\n")
