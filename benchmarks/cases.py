"""Versioned CPU workloads. Expectations are independent of the timed sources.

The original 202 matching fixtures, 56 whole-stack audit additions, and PR #21
review controls are kept together so every ref runs exactly the same inputs.
See README.md for the claim-to-case inventory and provenance.
"""

from datetime import date
from decimal import Decimal
import re
import sys
from uuid import UUID


CASES = [
    ("flat", {"x": 73}, {"x": 73}),
    ("deep", {"a.b.c.d.e": 73}, {"a": {"b": {"c": {"d": {"e": 73}}}}}),
    ("subdocuments", {"items.x": 73}, {"items": [{"x": i} for i in range(100)]}),
    ("large-in", {"x": {"$in": list(range(1000))}}, {"x": 999}),
    ("regex", {"x": {"$regex": "^item-[0-9]+$"}}, {"x": "item-73"}),
    ("regex-unicode-ignorecase", {"x": {"$regex": "^über$", "$options": "i"}}, {"x": "Über"}),
    ("regex-unicode-class", {"x": {"$regex": r"^\w+$"}}, {"x": "äpfel"}),
    ("and-or", {"$and": [{"x": {"$gt": 10}}, {"$or": [{"y": 0}, {"y": 2}]}]},
     {"x": 73, "y": 2}),
    ("indexed-eq", {"a.9.x": 73}, {"a": [{"x": i} for i in range(9)] + [{"x": 73}]}),
    ("indexed-eq-multi", {"a.73.x": 73}, {"a": [{"x": i} for i in range(100)]}),
    ("size", {"x": {"$size": 2}}, {"x": [1, 2]}),
    ("deep-size", {"a.b.c.d.e": {"$size": 2}},
     {"a": {"b": {"c": {"d": {"e": [1, 2]}}}}}),
    ("mod", {"x": {"$mod": [3, 1]}}, {"x": 73}),
    ("deep-mod", {"a.b.c.d.e": {"$mod": [3, 1]}},
     {"a": {"b": {"c": {"d": {"e": 73}}}}}),
    ("array-mod", {"x": {"$mod": [3, 1]}}, {"x": list(range(100))}),
    ("array-mod-last", {"x": {"$mod": [3, 1]}}, {"x": [0] * 99 + [1]}),
    ("ordered-document", {"x": {"a": 1, "b": [2, 3]}}, {"x": {"a": 1, "b": [2, 3]}}),
    ("array-range", {"x": {"$gt": [1, 2]}}, {"x": [1, 3]}),
    ("document-range", {"x": {"$gt": {"a": 1}}}, {"x": {"a": 2}}),
    ("all", {"x": {"$all": [72, 73]}}, {"x": list(range(100))}),
    ("all-string", {"x": {"$all": ["t72", "t73"]}},
     {"x": [f"t{i}" for i in range(100)]}),
    ("date", {"x": "2024-08-01"}, {"x": date(2024, 8, 1)}),
    ("decimal", {"x": {"$gte": "3.14"}}, {"x": Decimal("3.14")}),
    ("uuid", {"x": "0123456789abcdef0123456789abcdef"},
     {"x": UUID("0123456789abcdef0123456789abcdef")}),
    ("elem-match-value", {"x": {"$elemMatch": {"$gt": 72, "$lt": 74}}},
     {"x": list(range(100))}),
    ("empty-suffix", {"x.": 73}, {"x": [73]}),
    ("all-singleton", {"x": {"$all": [73]}}, {"x": list(range(100))}),
]


MATCH_CASES = [(name, query, doc, True) for name, query, doc in CASES]
for op, hit, miss in (("$gt", 73, 0), ("$gte", 73, 0), ("$lt", 71, 99), ("$lte", 71, 99)):
    for direction, operand, cast in (("int-float", 72, float), ("float-int", 72.0, int)):
        query = {"x": {op: operand}}
        for shape, value, expected in (
            ("scalar", cast(hit), True),
            ("scalar-miss", cast(miss), False),
            ("array-last", [cast(miss)] * 99 + [cast(hit)], True),
            ("array-miss", [cast(miss)] * 100, False),
        ):
            MATCH_CASES.append((f"{op[1:]}-{direction}-{shape}", query, {"x": value}, expected))


for name, expression, hit, miss in (
    ("eq", 73, 73, 0), ("in", {"$in": [72, 73]}, 73, 0),
    ("exists", {"$exists": True}, None, None),
    ("size", {"$size": 2}, [1, 2], [1]),
    ("all", {"$all": [1, 2]}, [1, 2], [1]),
    ("elem-match", {"$elemMatch": {"a": 73}}, [{"a": 73}], [{"a": 0}]),
):
    prefix = {} if name == "exists" else {"y": miss}
    for position in (0, 99, None):
        values = [prefix] * 100
        if position is not None:
            values[position] = {"y": hit}
        MATCH_CASES.append((f"path-{name}-{position}", {"x.y": expression}, {"x": values}, position is not None))

MATCH_CASES.extend([
    ("numeric-field", {"x.0.y": 73}, {"x": [{"0": {"y": 73}}]}, True),
    ("indexed-miss", {"x.73.y": 73}, {"x": [{"y": 0}] * 100}, False),
    ("scalar-array-null", {"x.y": None}, {"x": [1] * 100}, False),
    ("nested-leaf", {"x": 73}, {"x": [[73]] * 100}, False),
    ("missing-null", {"a.b.c": None}, {}, True),
    ("empty-all", {"x.y": {"$all": []}}, {"x": [{"y": []}] * 100}, False),
    ("empty-all-negated", {"x.y": {"$not": {"$all": []}}}, {"x": [{"y": []}] * 100}, True),
])


MATCH_CASES.extend([
    ("indexed-list-leaf", {"x.0.0": 1}, {"x": [[1]]}, True),
    ("indexed-list-field", {"x.0.y": 1}, {"x": [[{"y": 1}]]}, True),
    ("indexed-list-index-field", {"x.0.0.y": 1}, {"x": [[{"y": 1}]]}, True),
    ("indexed-list-size", {"x.0.y": {"$size": 1}}, {"x": [[{"y": [1]}]]}, True),
    ("indexed-list-all", {"x.0.y": {"$all": [1, 2]}}, {"x": [[{"y": [1, 2]}]]}, True),
    ("indexed-list-terminal", {"x.0": [1]}, {"x": [[1]]}, True),
])
for depth in (4, 8, 16):
    value = 1
    for _ in range(depth):
        value = [value]
    MATCH_CASES.append((f"indexed-list-depth-{depth}", {"x" + ".0" * depth: 1}, {"x": value}, True))


for name, operand, hit, miss in (
    ("string", "target", "target", "other"),
    ("document", {"a": [1, 2]}, {"a": [1, 2]}, {"a": [1, 3]}),
    ("array", [1, {"a": 2}], [1, {"a": 2}], [1, {"a": 3}]),
    ("native-document", {"a": ["3.14"]}, {"a": [Decimal("3.14")]}, {"a": [Decimal("3.15")]}),
):
    for position in (0, 99, None):
        values = [miss] * 100
        if position is not None:
            values[position] = hit
        MATCH_CASES.append((f"value-{name}-{position}", {"x": operand}, {"x": values}, position is not None))

for name, first, second, miss in (("number", 72, 73, 0), ("string", "t72", "t73", "other")):
    for position in (0, 98, None):
        values = [miss] * 100
        if position is None:
            values[-1] = first
        else:
            values[position:position + 2] = [first, second]
        MATCH_CASES.append((f"all-{name}-{position}", {"x": {"$all": [first, second]}},
                            {"x": values}, position is not None))
    for length in (10_000, 100_000):
        MATCH_CASES.append((f"all-{name}-prefix-{length}", {"x": {"$all": [first, second]}},
                            {"x": [first, second] + [miss] * (length - 2)}, True))
    MATCH_CASES.append((f"all-{name}-shifted-prefix", {"x": {"$all": [second, first]}},
                        {"x": [miss] * 17 + [first, second] + [miss] * 9981}, True))

for op, number, other in (("$gt", 2, 0), ("$gte", 1, 0), ("$lt", 0, 2), ("$lte", 1, 2)):
    for name, operand, hit, miss in (
        ("document", {"a": 1}, {"a": number}, {"a": other}),
        ("binary", b"b", bytes([97 + number]), bytes([97 + other])),
    ):
        for position in (99, None):
            values = [miss] * 100
            if position is not None:
                values[position] = hit
            MATCH_CASES.append((f"range-{name}-{op[1:]}-{position}", {"x": {op: operand}},
                                {"x": values}, position is not None))

for name, operand, hit, miss in (
    ("date", "2024-08-01", date(2024, 8, 1), date(2024, 7, 31)),
    ("uuid", "0123456789abcdef0123456789abcdef",
     UUID("0123456789abcdef0123456789abcdef"), UUID(int=0)),
):
    for position in (99, None):
        values = [miss] * 100
        if position is not None:
            values[position] = hit
        MATCH_CASES.append((f"value-{name}-{position}", {"x": operand}, {"x": values}, position is not None))

MATCH_CASES.extend([
    ("bool-not-number", {"x": 1}, {"x": True}, False),
    ("nan-equality", {"x": float("nan")}, {"x": float("nan")}, True),
    ("nan-direct-range", {"x": {"$lte": float("nan")}}, {"x": float("nan")}, True),
    ("nan-array-range", {"x.0": {"$lt": [0]}}, {"x": [[float("nan")]]}, True),
    ("type-before-key", {"x": {"$gt": {"z": 1}}}, {"x": {"a": "x"}}, True),
    ("all-scalar", {"x": {"$all": [1]}}, {"x": 1}, True),
    ("all-branches", {"x.y": {"$all": [1, 2]}}, {"x": [{"y": 1}, {"y": 2}]}, True),
    ("all-native", {"x": {"$all": ["3.14"]}}, {"x": [Decimal("3.14")]}, True),
    ("native-container-range", {"x": {"$gte": {"a": ["3.14"]}}},
     {"x": {"a": [Decimal("3.14")]}}, True),
])


for name, operand, hit, miss in (
    ("number", 73, 73, 0), ("string", "target", "target", "other"),
    ("regex", re.compile("^target$"), "target", "other"),
    ("document", {"a": [1, 2]}, {"a": [1, 2]}, {"a": [1, 3]}),
    ("array", [1, 2], [1, 2], [1, 3]),
    ("date", "2024-08-01", date(2024, 8, 1), date(2024, 7, 31)),
):
    for position in (0, 99, None):
        values = [miss] * 100
        if position is not None:
            values[position] = hit
        MATCH_CASES.append((f"all-singleton-{name}-{position}", {"x": {"$all": [operand]}},
                            {"x": values}, position is not None))

for name, expression, hit, miss in (
    ("range", {"$gt": 72, "$lt": 74}, 73, 0),
    ("nested", {"$elemMatch": {"$eq": 73}}, [73], [0]),
    ("all", {"$all": [73, 73]}, 73, 0),
):
    for position in (0, 99, None):
        values = [miss] * 100
        if position is not None:
            values[position] = hit
        MATCH_CASES.append((f"elem-match-value-{name}-{position}", {"x": {"$elemMatch": expression}},
                            {"x": values}, position is not None))

MATCH_CASES.extend([
    ("all-elem-match-document", {"x": {"$all": [{"$elemMatch": {"a": 72}}, {"$elemMatch": {"a": 73}}]}},
     {"x": [{"a": i} for i in range(100)]}, True),
    ("all-elem-match-value", {"x": {"$all": [{"$elemMatch": {"$lt": 1}}, {"$elemMatch": {"$gt": 98}}]}},
     {"x": list(range(100))}, True),
    ("all-elem-match-mixed", {"x": {"$all": [{"$elemMatch": {"a": 73}}, {"$elemMatch": {"$eq": 74}}]}},
     {"x": [{"a": i} for i in range(100)] + [74]}, True),
    ("empty-suffix-size", {"x.": {"$size": 2}}, {"x": [72, 73]}, True),
    ("empty-suffix-all", {"x.": {"$all": [72, 73]}}, {"x": [72, 73]}, True),
    ("empty-suffix-indexed", {"x.0.": 73}, {"x": [[73]]}, True),
    ("empty-suffix-miss", {"x.": 73}, {"x": [{"": 73}] * 100}, False),
])


for name, expression, hit in (("size", {"$size": 0}, []),
                               ("elem-match", {"$elemMatch": {"$eq": 1}}, [1])):
    for position in (0, 99, None):
        values = [[0]] * 100
        if position is not None:
            values[position] = hit
        MATCH_CASES.append((f"empty-suffix-indexed-{name}-{position}", {"x.0.": expression},
                            {"x": [values]}, position is not None))


for name, cast in (("float", float), ("decimal", Decimal)):
    for shape, value, expected in (("scalar", cast(73), True),
                                    ("early", [cast(73)] + [cast(0)] * 99, True),
                                    ("last", [cast(0)] * 99 + [cast(73)], True),
                                    ("miss", [cast(0)] * 100, False)):
        MATCH_CASES.append((f"mod-{name}-{shape}", {"x": {"$mod": [3, 1]}}, {"x": value}, expected))


for name, value in (("string", "0"), ("null", None), ("document", {}),
                     ("bool", True), ("complex", 1j), ("decimal-large", Decimal("1E+5000"))):
    MATCH_CASES.append((f"mod-reject-{name}", {"x": {"$mod": [3, 1]}}, {"x": [value] * 100}, False))


for shape, value in (("scalar", Decimal("sNaN")), ("scan", [Decimal("sNaN")] * 100)):
    MATCH_CASES.append((f"mod-snan-{shape}", {"x": {"$mod": [3, 0]}}, {"x": value}, False))


# Whole-stack audit additions (also used by the 1.0.2 author).
MATCH_CASES.extend([
    ("flat-miss", {"x": 73}, {"x": 0}, False),
    ("flat-missing", {"x": 73}, {}, False),
    ("deep-miss", {"a.b.c.d.e": 73}, {"a": {"b": {"c": {"d": {"e": 0}}}}}, False),
    ("deep-missing", {"a.b.c.d.e": 73}, {"a": {}}, False),
])
for name, expression, hit, miss in (
    ("numeric", {"$gt": 72}, 73, 0),
    ("mixed", {"$gt": 72.0}, 73, 0),
    ("mod-scan", {"$mod": [3, 1]}, 1, 0),
    ("regex-scan", {"$regex": "^target$"}, "target", "other"),
    ("implicit-regex", re.compile("^target$"), "target", "other"),
    ("date-scan", "2024-08-01", date(2024, 8, 1), date(2024, 7, 31)),
    ("uuid-scan", "0123456789abcdef0123456789abcdef",
     UUID("0123456789abcdef0123456789abcdef"), UUID(int=0)),
    ("elem-document", {"$elemMatch": {"a": 73}}, {"a": 73}, {"a": 0}),
    ("document-scan", {"a": 1, "b": 2}, {"a": 1, "b": 2}, {"a": 1, "b": 3}),
    ("document-range-scan", {"$gt": {"a": 72}}, {"a": 73}, {"a": 0}),
    ("array-range-scan", {"$lt": [72]}, [0], [99]),
):
    for label, position in (("early", 0), ("last", 99), ("miss", None)):
        values = [miss] * 100
        if position is not None:
            values[position] = hit
        MATCH_CASES.append((name + "-" + label, {"x": expression}, {"x": values}, position is not None))

for label, index in (("early", 0), ("last", 999), ("miss", 1000)):
    MATCH_CASES.append(("in-1000-" + label, {"x": {"$in": list(range(1000))}},
                        {"x": index}, index < 1000))

for name, position, expected in (("and-early", 0, False), ("and-last", 99, False),
                                ("and-hit", None, True), ("or-early", 0, True),
                                ("or-last", 99, True), ("or-miss", None, False)):
    is_and = name.startswith("and")
    children = [{"x" + str(i): 1} for i in range(100)]
    document = {"x" + str(i): int(is_and) for i in range(100)}
    if position is not None:
        document["x" + str(position)] = int(not is_and)
    MATCH_CASES.append((name, {"$and" if is_and else "$or": children}, document, expected))

for label, position in (("early", 0), ("last", 99), ("miss", None)):
    values = [{"y": 0}] * 100
    if position is not None:
        values[position] = {"y": 73}
    MATCH_CASES.append(("subdocs-" + label, {"x.y": 73}, {"x": values}, position is not None))
    values = [{"y": 0}] * 100
    if position is not None:
        values[position] = {"73": {"y": 73}}
    MATCH_CASES.append(("index-alternative-" + label, {"x.73.y": 73}, {"x": values}, position is not None))

MATCH_CASES.extend([
    ("ordered-key-mismatch", {"x": {"a": 1, "b": 2}}, {"x": {"b": 2, "a": 1}}, False),
    ("mod-negative", {"x": {"$mod": [3, -1]}}, {"x": -4}, True),
    ("array-range-element-miss", {"x.0": {"$gt": [1, 2]}}, {"x": [[1, 1]]}, False),
    ("document-range-key", {"x": {"$gt": {"a": 0}}}, {"x": {"b": 0}}, True),
])

# PR #21 review. Existing document-scan-* and in-1000-* cover duplicate rows.
MATCH_CASES.extend([
    ("review-wide-and", {"$and": [{f"x{i}": 1} for i in range(100)]}, {"x0": 0}, False),
    ("review-compiled-regex", {"x": re.compile("^über$", re.I)}, {"x": "Über"}, True),
    ("review-flat-list", {"x": {"$eq": [1, None, 3.0]}}, {"x": [1, None, 3]}, True),
])
for count in (1, 2, 10):
    for position in sorted({0, count - 1, count}):
        MATCH_CASES.append((f"review-in-{count}-{position}", {"x": {"$in": list(range(count))}},
                            {"x": position}, position < count))

for count in (100, 1000, 3000):
    # Exact Python ints with identical hashes; intentionally outside BSON int64.
    values = [i * sys.hash_info.modulus for i in range(count)]
    for op in ("in", "nin"):
        MATCH_CASES.append((f"review-{op}-collisions-{count}", {"x": {"$" + op: values}},
                            {"x": values[-1]}, op == "in"))

for count in (100, 1000, 10_000):
    dictionary = {f"a{i}": 1 for i in range(count)}
    MATCH_CASES.extend([
        (f"review-wide-dict-empty-{count}", {"x": {}}, {"x": dictionary}, False),
        (f"review-wide-list-empty-{count}", {"x.0": {"$eq": []}}, {"x": [[1] * count]}, False),
        (f"review-wide-dict-first-mismatch-{count}", {"x": {**dictionary, "a0": 0}},
         {"x": dictionary}, False),
        (f"review-wide-list-first-mismatch-{count}", {"x.0": {"$eq": [0] + [1] * (count - 1)}},
         {"x": [[1] * count]}, False),
        # Whole-document width, distinct from comparing a wide embedded value.
        (f"wide-document-hit-{count}", {f"a{count - 1}": 1}, dictionary, True),
        (f"wide-document-miss-{count}", {"absent": 1}, dictionary, False),
        (f"construct-in-{count}", {"x": {"$in": list(range(count))}}, {"x": count - 1}, True),
        (f"construct-and-{count}", {"$and": [{f"a{i}": 1} for i in range(count)]},
         {"a0": 0}, False),
    ])


class FoldKey(str):
    """The PR #21 thermos result-changing key control."""

    def __eq__(self, other):
        return self.casefold() == str(other).casefold()

    def __hash__(self):
        return hash(self.casefold())


MATCH_CASES.extend([
    ("review-subclass-key-eq", {"x": {"$eq": {"a": 1}}}, {"x": {FoldKey("A"): 1}}, False),
    ("review-subclass-key-ne", {"x": {"$ne": {"a": 1}}}, {"x": {FoldKey("A"): 1}}, True),
])

# Same-type/deep controls reconstructed from the original mixed-numeric gate.
for op, hit in (("$gt", 73), ("$gte", 72), ("$lt", 71), ("$lte", 72)):
    for label, cast in (("int", int), ("float", float)):
        MATCH_CASES.append((f"{op[1:]}-{label}-{label}-scalar", {"x": {op: cast(72)}},
                            {"x": cast(hit)}, True))
MATCH_CASES.append(("deep-mixed-range", {"a.b.c.d.x": {"$gt": 72}},
                    {"a": {"b": {"c": {"d": {"x": 73.0}}}}}, True))

assert len({row[0] for row in MATCH_CASES}) == len(MATCH_CASES)


def cases(filters=()):
    """Select by shell-style case-name glob, retaining stable seed positions."""
    from fnmatch import fnmatchcase

    return [(index, row) for index, row in enumerate(MATCH_CASES)
            if not filters or any(fnmatchcase(row[0], pattern) for pattern in filters)]
