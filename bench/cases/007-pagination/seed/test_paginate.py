from paginate import paginate

result = paginate(list(range(10)), page=2, per_page=5)
assert result["items"] == [5, 6, 7, 8, 9]
assert result["pages"] == 2
assert result["has_next"] is False
print("ok")
