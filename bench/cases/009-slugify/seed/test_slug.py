from slug import slugify

assert slugify("Hello   World") == "hello-world"
print("ok")
