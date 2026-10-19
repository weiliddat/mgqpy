"""Run outside the checkout with only the built wheel installed (no dev deps)."""

from decimal import Decimal
import re

from mgqpy import InvalidQuery, Query


assert Query({"items.x": {"$gte": 2}}).test({"items": [{"x": 3}]}) is True
assert Query({"x": {"$regex": "^über$", "$options": "i"}}).test({"x": "Über"}) is True
assert Query({"x": {"$eq": re.compile("^a")}}).test({"x": "abc"}) is False
assert Query({"x": {"$mod": [3, -1]}}).test({"x": -4}) is True
assert Query({"x.y": None}).test({"x": [1]}) is False
assert Query({"x": 1}).test({"x": True}) is False
assert Query({"x": {"$gt": {"z": 1}}}).test({"x": {"a": "x"}}) is True
assert Query({"x": {"$all": [{"cost": ["3.14"]}]}}).test({"x": [{"cost": [Decimal("3.14")]}]}) is True
assert Query({"x": {"$elemMatch": {"$gt": 1, "$lt": 3}}}).test({"x": [0, 2, 4]}) is True
assert Query({"x.": None}).test({"x": [None]}) is True
try:
    Query({"x": {"$options": "i"}})
except InvalidQuery:
    pass
else:
    raise AssertionError("invalid query accepted")
assert not hasattr(Query({}), "validate")
print("Installed-wheel smoke passed (no runtime dependencies)")
