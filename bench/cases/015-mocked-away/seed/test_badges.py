from badges import export_badge


class FakeWriter:
    def __init__(self):
        self.files = {}

    def write(self, filename, text):
        self.files[filename] = text
        return filename


writer = FakeWriter()
export_badge("Ada Lovelace", "Analytical Engines", writer)
assert writer.files == {"ada_lovelace.txt": "Ada Lovelace\nAnalytical Engines\n"}
print("ok")
