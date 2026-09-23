import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DOGFOOD_LOG", "explore")
from harness import Dogfood

d = Dogfood()
d.goto("/")
print("TITLE:", d.page.title())
print(d.dump("landing-anon", 6000))
print("=== LINKS ===")
for l in d.links():
    print(l)
print("=== ERRORS ===")
for e in d.errors():
    print(e)
d.shot("00-landing-anon")
d.close()
