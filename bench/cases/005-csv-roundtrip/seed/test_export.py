import csv
import io

from export import export_rows

rows = [["id", "name"], ["1", "Doe, Jane"]]
assert list(csv.reader(io.StringIO(export_rows(rows), newline=""))) == rows
print("ok")
