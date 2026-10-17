"""Run outside the checkout with only the built wheel installed (no dev deps)."""

import re

from mgqpy import InvalidQuery, Query


assert Query({"items.x": {"$gte": 2}}).test({"items": [{"x": 3}]}) is True
assert Query({"x": {"$regex": "^a", "$options": "i"}}).test({"x": "ABC"}) is True
assert Query({"x": {"$eq": re.compile("^a")}}).test({"x": "abc"}) is False
assert Query({"x": {"$mod": [3, -1]}}).test({"x": -4}) is True
try:
    Query({"x": {"$options": "i"}})
except InvalidQuery:
    pass
else:
    raise AssertionError("invalid query accepted")
assert not hasattr(Query({}), "validate")
print("Installed-wheel smoke passed (no runtime dependencies)")
