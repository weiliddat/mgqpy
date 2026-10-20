"""Deterministic compatibility corpus: documents, queries and their area tags.

`probe` rows reproduce the real-server differential used for the mgqpy 1.0.2
review (`random.Random(50023)`); mgqpy was developed against it. `new` rows were
added for this comparison and were not used to develop any library.
"""

import copy
from datetime import datetime
import random
import re


SCALARS = [None, False, True, -1, 0, 1, 2, 1.0, float("nan"),
           -float("inf"), float("inf"), "", "a", "b", b"a", b"zz",
           datetime(2024, 8, 1), re.compile("a"), re.compile("a", re.I)]
VALUES = SCALARS + [[], [None], [0], [1], [1, 2], [[1]], [[1, 2]],
                    {}, {"a": 1}, {"a": 1, "b": 2}, {"b": 2, "a": 1},
                    {"0": 1}, {"": 1}, {"y": 1}, {"a": [1]}, [{"a": 1}],
                    [True, 1], [float("nan")], {"a": "a"}, {"a": None}]
# New: cross-type numbers, strings that look like numbers, case, Unicode, dates.
NEW_VALUES = ["1", 1.5, 2 ** 53 + 1, float(2 ** 53), -0.0, "A", "ab", "é",
              datetime(2024, 8, 2), {"a": {"b": 1}}, [[]], [None, 1], [1, "a"]]
SHAPES = (lambda v: {"x": v}, lambda v: {"x": [v]}, lambda v: {"x": [0, v]},
          lambda v: {"x": [v, {}]}, lambda v: {"x": {"0": v, "y": v, "": v}},
          lambda v: {"x": [{"0": v}, {"y": v}, {"": v}]})


def documents():
    docs = [{}]
    for value in VALUES:
        docs += [shape(value) for shape in SHAPES]
    rng = random.Random(50023)

    def nested(depth):
        if not depth or rng.random() < .45:
            return copy.deepcopy(rng.choice(VALUES))
        if rng.random() < .5:
            return [nested(depth - 1) for _ in range(rng.randrange(4))]
        return {key: nested(depth - 1)
                for key in rng.sample(["0", "1", "00", "", "y", "a"], rng.randrange(4))}

    docs += [{"x": nested(3)} for _ in range(180)]
    for value in NEW_VALUES:
        docs += [shape(value) for shape in SHAPES]
    docs += [{"x": None, "y": 1}, {"y": 1}, {"x": {"y": None}}, {"x": [{"y": None}, {"y": 1}]},
             {"x": [{"z": 1}]}, {"x": {"y": [1, 2, 3]}}, {"x": {"y": {"z": [1, {"w": 2}]}}},
             {"x": [[{"y": 1}]]}, {"x": [{"y": [{"z": 1}]}]}, {"x": "Abc\ndef"},
             {"x": ["abc", "ABC", "xyz"]}, {"x": [1, 2, 3, 4]}, {"x": [3, 1]}]
    return docs


def queries():
    """Return [(origin, query)]. Areas are derived from the query by classify()."""
    rows = []
    expressions = []
    for operand in VALUES:
        expressions += [{op: operand} for op in ("$eq", "$ne", "$gt", "$gte", "$lt", "$lte")]
        expressions += [{"$in": [operand]}, {"$nin": [operand]}, {"$all": [operand]}]
    for operands in ([1, 2], [2, 1], [None, 1], [1, True], [re.compile("a"), "b"],
                     [[1], [2]], [{"a": 1}, {"b": 2}]):
        expressions += [{"$all": operands}, {"$in": operands}, {"$nin": operands}]
    expressions += [{"$size": n} for n in range(4)]
    expressions += [{"$mod": pair} for pair in ([3, 1], [-3, -1], [1.5, 0.9])]
    expressions += [{"$exists": v} for v in (True, False, None, 0, "", [], {})]
    expressions += [{"$regex": "a"}, {"$regex": "^a$", "$options": "i"},
                    {"$not": {"$gt": 1, "$lt": 3}}, {"$eq": 1, "$ne": 2},
                    {"$elemMatch": {}}, {"$elemMatch": {"y": 1}},
                    {"$elemMatch": {"0": 1}}, {"$elemMatch": {"": 1}},
                    {"$elemMatch": {"$gt": 0, "$lt": 2}},
                    {"$elemMatch": {"$not": {"$eq": 1}}},
                    {"$elemMatch": {"$all": [1, 2]}},
                    {"$elemMatch": {"$all": [[1, 2]]}},
                    {"$elemMatch": {"$elemMatch": {"y": 1}}},
                    {"$elemMatch": {"$or": [{"y": 1}, {"0": None}]}},
                    {"$all": [{"$elemMatch": {"$eq": 1}}, {"$elemMatch": {"y": 1}}]}]
    paths = ["x", "x.y", "x.0", "x.1", "x.0.y", "x.0.0", "x.0.",
             "x.", "x..", "x..y", "x.00", "x.10000000000000000000000"]
    rows += [("probe", {path: e}) for path in paths for e in expressions]
    rows += [("probe", {"$or": [{"x.y": e}, {"x.0": None}]}) for e in expressions[::5]]
    rows += [("probe", {"$nor": [{"x.0.": e}, {"x.y": None}]}) for e in expressions[::5]]

    new = []
    for operand in NEW_VALUES:
        for op in ("$eq", "$ne", "$gt", "$gte", "$lt", "$lte", "$in", "$nin", "$all"):
            e = {op: [operand]} if op in ("$in", "$nin", "$all") else {op: operand}
            new += [{path: e} for path in ("x", "x.y", "x.0")]
        new.append({"x": operand})
    # Implicit equality, implicit regex and null/missing.
    for operand in VALUES:
        new += [{"x": operand}, {"x.y": operand}]
    new += [{"x": None}, {"x.y": None}, {"x.0": None}, {"x.y.z": None},
            {"x": {"$ne": None}}, {"x.y": {"$ne": None}}, {"x": {"$in": [None, 1]}},
            {"x.y": {"$nin": [None]}}, {"x": {"$gte": None}}, {"x": {"$lt": None}},
            {"x.y": {"$exists": True}}, {"x.y.z": {"$exists": False}},
            {"x.y": {"$size": 3}}, {"x.y.z": {"$size": 2}}, {"x.y.z.w": 2},
            {"x.y.z": 1}, {"x.0.y": 1}, {"x.0.y.0.z": 1}, {"x.y.0": 1}, {"x.y.2": 3}]
    # $type: numeric codes, aliases and lists.
    for t in (1, 2, 3, 4, 5, 8, 9, 10, 11, 16, 18, "double", "string", "object", "array",
              "binData", "bool", "date", "null", "regex", "int", "long", "number", [2, 4]):
        new += [{"x": {"$type": t}}, {"x.y": {"$type": t}}]
    # Regex options, implicit regex, regex in membership and negation.
    for pattern in ("^a", "a$", "^A", "b|z", "^$", "^\\w$", "^.$", "d", "^def", "/a/i"):
        for options in (None, "i", "m", "s", "x", "im"):
            e = {"$regex": pattern} if options is None else {"$regex": pattern, "$options": options}
            new.append({"x": e})
    for pattern in (re.compile("^a"), re.compile("^A", re.I), re.compile("^def", re.M),
                    re.compile("c.d", re.S), re.compile("^\\w$")):
        new += [{"x": pattern}, {"x": {"$regex": pattern}}, {"x": {"$in": [pattern, 1]}},
                {"x": {"$nin": [pattern]}}, {"x": {"$not": pattern}}, {"x.y": pattern},
                {"x": {"$all": [pattern]}}, {"x": {"$elemMatch": {"$regex": pattern}}}]
    # Logical combinations.
    leaves = [{"x": 1}, {"x": {"$gt": 1}}, {"x": None}, {"x.y": 1}, {"y": 1},
              {"x": {"$exists": False}}, {"x": {"$size": 2}}, {"x": "a"}]
    for i, a in enumerate(leaves):
        for b in leaves[i + 1:]:
            new += [{"$and": [a, b]}, {"$or": [a, b]}, {"$nor": [a, b]}]
    new += [{"$and": [{"$or": [{"x": 1}, {"x": 2}]}, {"$nor": [{"x": None}]}]},
            {"$or": [{"$and": [{"x": {"$gte": 1}}, {"x": {"$lte": 2}}]}, {"y": 1}]},
            {"x": 1, "$or": [{"y": 1}, {"x": 2}]}, {"$and": [{"x": {"$gt": 0}}, {"x": {"$lt": 2}}]}]
    for e in ({"$eq": 1}, {"$gt": 1}, {"$in": [1, 2]}, {"$size": 1}, {"$exists": True},
              {"$regex": "a"}, {"$elemMatch": {"$gt": 1}}, {"$all": [1]}, {"$mod": [2, 0]},
              {"$type": "string"}, {"$eq": None}, {"$in": [None]}):
        new += [{"x": {"$not": e}}, {"x.y": {"$not": e}}]
    # Arrays: whole-array equality, nested arrays, $all/$elemMatch/$size combinations.
    new += [{"x": [1, 2]}, {"x": [2, 1]}, {"x": [[1, 2]]}, {"x": []}, {"x": [[]]},
            {"x": {"$all": [1, 2, 3]}}, {"x": {"$all": [[1, 2]]}}, {"x": {"$all": []}},
            {"x": {"$size": 4}}, {"x": {"$size": 2, "$all": [1]}},
            {"x": {"$elemMatch": {"$gte": 2, "$lte": 3}}}, {"x": {"$elemMatch": {"y": None}}},
            {"x": {"$elemMatch": {"y": {"$exists": False}}}}, {"x": {"$elemMatch": {"z": 1}}},
            {"x.y": {"$elemMatch": {"z": 1}}}, {"x": {"$elemMatch": {"y.z": 1}}},
            {"x": {"$elemMatch": {"y": {"$elemMatch": {"z": 1}}}}},
            {"x": {"$gt": 1, "$lt": 3}}, {"x": {"$elemMatch": {"$gt": 1, "$lt": 3}}},
            {"x": {"$in": [[1, 2], 3]}}, {"x": {"$nin": [[1, 2], 3]}},
            {"x": {"$mod": [2, 1]}}, {"x": {"$mod": [2.5, 0]}}, {"x": {"$mod": [-2, 0]}}]
    rows += [("new", q) for q in new]
    rows += [("invalid", q) for q in INVALID]
    return rows


INVALID = [
    {"x": {"$in": 1}}, {"x": {"$nin": "a"}}, {"x": {"$all": 1}}, {"$and": []}, {"$or": []},
    {"$nor": []}, {"$and": {}}, {"$or": [1]}, {"$and": [{"x": 1}, 2]}, {"x": {"$foo": 1}},
    {"$foo": 1}, {"x": {"$size": -1}}, {"x": {"$size": 1.5}}, {"x": {"$size": "a"}},
    {"x": {"$mod": [0, 1]}}, {"x": {"$mod": [1]}}, {"x": {"$mod": "a"}}, {"x": {"$mod": [1, 2, 3]}},
    {"x": {"$regex": "("}}, {"x": {"$regex": 1}}, {"x": {"$options": "i"}},
    {"x": {"$regex": "a", "$options": "z"}}, {"x": {"$elemMatch": 1}}, {"x": {"$not": 1}},
    {"x": {"$not": {}}}, {"x": {"$exists": True, "$bad": 1}}, {"x": {"$type": "nope"}},
    {"x": {"$type": 99}}, {"x": {"$type": []}}, {"x": {"$eq": 1, "y": 2}},
    {"x": {"$in": [{"$gt": 1}]}}, {"x": {"$all": [{"$elemMatch": {"y": 1}}, 1]}},
    {"x": {"$not": {"$foo": 1}}}, {"x": {"$elemMatch": {"$foo": 1}}}, {"$or": [{"x": {"$foo": 1}}]},
    {"x": {"$gt": 1, "$in": 1}},
]


PATH_CLASSES = (("x", "top-level"), ("x.y", "dotted"), ("x.y.z", "dotted"),
                ("x.y.z.w", "dotted"))


def classify(query):
    """Return (operator area, path class, operand class) for a query."""
    if any(k in query for k in ("$and", "$or", "$nor")):
        return "logical", "mixed", "mixed"
    path, expression = next(iter(query.items()))
    parts = path.split(".")
    if path in ("x", "x.y", "x.y.z", "x.y.z.w"):
        path_class = "top-level field" if path == "x" else "dotted field"
    elif any(p == "" for p in parts):
        path_class = "empty component"
    elif all(p.isdigit() and (p == "0" or not p.startswith("0")) and len(p) < 19
             for p in parts if p.isdigit()) and any(p.isdigit() for p in parts):
        path_class = "numeric index"
    else:
        path_class = "noncanonical index"
    if isinstance(expression, dict) and expression and next(iter(expression)).startswith("$"):
        op = next(iter(expression))
        operand = expression[op]
    else:
        op, operand = ("$regex" if isinstance(expression, re.Pattern) else "$eq"), expression
    area = {"$eq": "equality", "$ne": "equality", "$gt": "range", "$gte": "range",
            "$lt": "range", "$lte": "range", "$in": "$in/$nin", "$nin": "$in/$nin",
            "$not": "logical", "$options": "$regex"}.get(op, op)
    if op in ("$in", "$nin", "$all") and isinstance(operand, list) and len(operand) == 1:
        operand = operand[0]
    return area, path_class, operand_class(operand)


def operand_class(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, float) and (value != value or value in (float("inf"), -float("inf"))):
        return "NaN/inf"
    if isinstance(value, (int, float)):
        return "number"
    return {str: "string", bytes: "binary", datetime: "date", list: "array",
            dict: "document"}.get(type(value), "regex" if isinstance(value, re.Pattern) else "other")


# Operator coverage: one canonical query per operator over simple documents.
COVERAGE_DOCUMENTS = [{"x": 1}, {"x": 2}, {"x": 3}, {"x": "abc"}, {"x": "ABC"}, {"x": [1, 2]},
                      {"x": [2, 3]}, {"x": {"y": 1}}, {"x": [{"y": 1}, {"y": 2}]}, {"x": None}, {},
                      {"x": 5, "z": 1}]
COVERAGE = [
    ("$eq", {"x": {"$eq": 2}}), ("implicit $eq", {"x": 2}), ("$ne", {"x": {"$ne": 2}}),
    ("$gt", {"x": {"$gt": 1}}), ("$gte", {"x": {"$gte": 2}}), ("$lt", {"x": {"$lt": 2}}),
    ("$lte", {"x": {"$lte": 2}}), ("$in", {"x": {"$in": [2, "abc"]}}), ("$nin", {"x": {"$nin": [2, "abc"]}}),
    ("$and", {"$and": [{"x": {"$gt": 1}}, {"x": {"$lt": 3}}]}), ("$or", {"$or": [{"x": 1}, {"x": "abc"}]}),
    ("$nor", {"$nor": [{"x": 1}, {"x": "abc"}]}), ("$not", {"x": {"$not": {"$gt": 1}}}),
    ("$exists", {"x": {"$exists": False}}), ("$type", {"x": {"$type": "string"}}),
    ("$regex", {"x": {"$regex": "^a"}}), ("$regex + $options", {"x": {"$regex": "^a", "$options": "i"}}),
    ("implicit regex", {"x": re.compile("^a", re.I)}), ("$mod", {"x": {"$mod": [2, 1]}}),
    ("$all", {"x": {"$all": [2, 3]}}), ("$elemMatch (value)", {"x": {"$elemMatch": {"$gt": 2}}}),
    ("$elemMatch (document)", {"x": {"$elemMatch": {"y": 2}}}), ("$size", {"x": {"$size": 2}}),
    ("dotted path", {"x.y": 2}), ("array index path", {"x.1": 3}),
    ("$expr", {"$expr": {"$gt": ["$x", "$z"]}}), ("$jsonSchema", {"$jsonSchema": {"required": ["z"]}}),
    ("$bitsAllSet", {"x": {"$bitsAllSet": 1}}), ("$bitsAnyClear", {"x": {"$bitsAnyClear": 1}}),
    ("$comment", {"x": 2, "$comment": "c"}),
]
