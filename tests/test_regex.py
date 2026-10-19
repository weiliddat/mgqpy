import re
import pytest

from mgqpy import Query

from .helpers import assert_matches, get_mongo_results, get_filter_results

testcases = [
    (
        "$regex",
        {
            "foo": {
                "$regex": "^ba",
            },
        },
        [
            {"foo": {}},
            {"foo": None},
            {"foo": 1},
            {"foo": "bar"},
            {"foo": "baz"},
            {"foo": "BAR"},
            {"foo": "BAZ"},
            {"foo": "qux"},
            {"foo": "quux"},
        ],
        [
            {"foo": "bar"},
            {"foo": "baz"},
        ],
    ),
    (
        "$regex with i flag",
        {
            "foo": {
                "$regex": "^ba",
                "$options": "i",
            },
        },
        [
            {"foo": "bar"},
            {"foo": "baz"},
            {"foo": "BAR"},
            {"foo": "BAZ"},
            {"foo": "qux"},
            {"foo": "quux"},
        ],
        [
            {"foo": "bar"},
            {"foo": "baz"},
            {"foo": "BAR"},
            {"foo": "BAZ"},
        ],
    ),
    (
        "$regex with s flag",
        {
            "foo": {
                "$regex": "bar.baz",
                "$options": "s",
            },
        },
        [
            {"foo": "bar_baz"},
            {"foo": "bar\nbaz"},
            {"foo": "bar baz"},
        ],
        [
            {"foo": "bar_baz"},
            {"foo": "bar\nbaz"},
            {"foo": "bar baz"},
        ],
    ),
    (
        "$regex with m flag",
        {
            "foo": {
                "$regex": "^baz",
                "$options": "m",
            },
        },
        [
            {"foo": "baz"},
            {"foo": "bar_baz"},
            {"foo": "bar\nbaz"},
            {"foo": "bar baz"},
        ],
        [
            {"foo": "baz"},
            {"foo": "bar\nbaz"},
        ],
    ),
    (
        "$regex with x flag",
        {
            "foo": {
                "$regex": "^ baz $",
                "$options": "x",
            },
        },
        [
            {"foo": "baz"},
            {"foo": "bar_baz"},
            {"foo": "bar\nbaz"},
            {"foo": "bar baz"},
        ],
        [
            {"foo": "baz"},
        ],
    ),
    (
        "$regex with nested dict/lists",
        {"foo.bar": {"$regex": "^baz"}},
        [
            {"foo": [{"bar": "bazo"}]},
            {"foo": {"bar": ["bazi"]}},
            {"foo": {"bar": ["qux", "bazqux"]}},
            {"foo": ["bar", "baz"]},
            {"foo": None},
            {},
        ],
        [
            {"foo": [{"bar": "bazo"}]},
            {"foo": {"bar": ["bazi"]}},
            {"foo": {"bar": ["qux", "bazqux"]}},
        ],
    ),
    (
        "$regex with indexed lists",
        {"foo.0.bar": {"$regex": "^baz"}},
        [
            {"foo": [{"bar": "bazo"}]},
            {"foo": {"bar": ["bazi"]}},
            {"foo": {"bar": ["qux", "bazqux"]}},
            {"foo": ["bar", "baz"]},
            {"foo": None},
            {},
        ],
        [
            {"foo": [{"bar": "bazo"}]},
        ],
    ),
    (
        "implicit $regex",
        {"foo": re.compile("^ba", re.IGNORECASE)},
        [
            {"foo": {}},
            {"foo": None},
            {"foo": 1},
            {"foo": "bar"},
            {"foo": "baz"},
            {"foo": "BAR"},
            {"foo": "BAZ"},
            {"foo": "qux"},
            {"foo": "quux"},
        ],
        [
            {"foo": "bar"},
            {"foo": "baz"},
            {"foo": "BAR"},
            {"foo": "BAZ"},
        ],
    ),
    (
        "implicit $regex with nested dict/lists",
        {"foo.bar": re.compile("^baz", re.IGNORECASE)},
        [
            {"foo": {}},
            {"foo": None},
            {"foo": 1},
            {"foo": "bar"},
            {"foo": {"bar": ["qux", "baz"]}},
            {"foo": [{"bar": ["qux"]}, {"bar": "baz"}]},
        ],
        [
            {"foo": {"bar": ["qux", "baz"]}},
            {"foo": [{"bar": ["qux"]}, {"bar": "baz"}]},
        ],
    ),
    (
        "$in with implicit $regex",
        {
            "foo": {
                "$in": [
                    re.compile("^ba", re.IGNORECASE),
                    re.compile("^qu", re.IGNORECASE),
                ]
            }
        },
        [
            {"foo": {}},
            {"foo": None},
            {"foo": 1},
            {"foo": "bar"},
            {"foo": "baz"},
            {"foo": "BAR"},
            {"foo": "BAZ"},
            {"foo": "qux"},
            {"foo": "quux"},
        ],
        [
            {"foo": "bar"},
            {"foo": "baz"},
            {"foo": "BAR"},
            {"foo": "BAZ"},
            {"foo": "qux"},
            {"foo": "quux"},
        ],
    ),
]


@pytest.mark.parametrize("name,query,input,expected", testcases)
def test_mgqpy_regex(test_db, name, query, input, expected):
    mongo_expected = get_mongo_results(test_db, query, input)
    assert expected == mongo_expected, name

    q = Query(query)
    actual = get_filter_results(q.test, input)
    assert actual == expected, name


@pytest.mark.parametrize("expression,values,hits", [
    ({"$regex": "äpfel", "$options": "i"}, ["Äpfel", "Apfel", "äpfel"], [0, 2]),
    ({"$regex": "öl", "$options": "i"}, ["Ölfilter", "Olfilter", "Olivenöl"], [0, 2]),
    ({"$regex": "^über$", "$options": "i"}, ["Über", "ÜBER", "Überraschung", "uber"], [0, 1]),
    ({"$regex": "^ß$", "$options": "i"}, ["ß", "SS", "ss"], [0]),
    (re.compile("äpfel", re.I), ["Äpfel", ["Apfel", "Äpfel"], "Apfel"], [0, 1]),
    ({"$regex": re.compile("^über$", re.I)}, ["Über", "überall"], [0]),
    ({"$in": [re.compile("öl", re.I)]}, ["Ölfilter", ["Olfilter", "Ölfilter"], "Olfilter"], [0, 1]),
    ({"$nin": [re.compile("öl", re.I)]}, ["Ölfilter", ["Olfilter", "Ölfilter"], "Olfilter"], [2]),
    ({"$not": re.compile("äpfel", re.I)}, ["Äpfel", "Apfel"], [1]),
    ({"$all": [re.compile("öl", re.I)]}, ["Ölfilter", ["Ölfilter"], "Olfilter"], [0, 1]),
    ({"$all": [re.compile("öl", re.I), re.compile("filter$")]},
     [["Ölfilter"], ["Öl", "filter"], ["Olfilter"]], [0, 1]),
    ({"$elemMatch": {"$regex": "^über$", "$options": "i"}},
     [["Über"], ["Überraschung"], [["Über"]]], [0]),
    ({"$regex": "(?P<word>a)"}, ["abc", "a", "2", "é", "١", "a\n", ""], [0, 1, 5]),
])
def test_regex_subset_against_mongo(test_db, expression, values, hits):
    assert_matches(test_db, {"x": expression}, [{"x": value} for value in values], hits)


@pytest.mark.parametrize("pattern,values,python_hits,mongo_hits", [
    (r"^\w+$", ["abc", "é", "١", "!", ""], [0, 1, 2], [0]),
    (r"^\d+$", ["2", "١", "é", ""], [0, 1], [0]),
    (r"^\s+$", [" ", "\u00a0", "\u2003", "x", ""], [0, 1, 2], [0]),
    (r"^\b(?:é|a)\b$", ["é", "a", "!", ""], [0, 1], [1]),
])
@pytest.mark.parametrize("mode", ["$regex", "compiled", "implicit", "$in", "$not"])
def test_unicode_classes_are_an_accepted_mongo_difference(
    test_db, pattern, values, python_hits, mongo_hits, mode,
):
    compiled = re.compile(pattern)
    expression = {
        "$regex": {"$regex": pattern, "$options": "u"},
        "compiled": {"$regex": compiled}, "implicit": compiled,
        "$in": {"$in": [compiled]}, "$not": {"$not": compiled},
    }[mode]
    if mode == "$not":
        python_hits = [i for i in range(len(values)) if i not in python_hits]
        mongo_hits = [i for i in range(len(values)) if i not in mongo_hits]
    documents = [{"x": value} for value in values]
    query = {"x": expression}
    assert get_mongo_results(test_db, query, documents) == [documents[i] for i in mongo_hits]
    assert get_filter_results(Query(query).test, documents) == [documents[i] for i in python_hits]


@pytest.mark.parametrize("flags", [0, re.I, re.A])
@pytest.mark.parametrize("operator", ["implicit", "$in", "$nin", "$not"])
def test_regex_literals_keep_original_flags(test_db, flags, operator):
    pattern = re.compile(r"^\w+$", flags)
    other = re.compile(pattern.pattern, (pattern.flags ^ re.ASCII) & ~re.UNICODE)
    expression = {
        "implicit": pattern, "$in": {"$in": [pattern]},
        "$nin": {"$nin": [pattern]}, "$not": {"$not": pattern},
    }[operator]
    documents = [
        {"case": "literal", "x": pattern}, {"case": "array", "x": [pattern]},
        {"case": "other-flags", "x": other}, {"case": "ascii", "x": "ABC"},
        {"case": "unicode", "x": "é"}, {"case": "missing"},
    ]
    mongo_hits = ["literal", "array", "ascii"]
    python_hits = mongo_hits if flags & re.ASCII else mongo_hits + ["unicode"]
    if operator in ("$nin", "$not"):
        mongo_hits = [d["case"] for d in documents if d["case"] not in mongo_hits]
        python_hits = [d["case"] for d in documents if d["case"] not in python_hits]
    query = {"x": expression}
    assert [d["case"] for d in get_mongo_results(test_db, query, documents)] == mongo_hits
    assert [d["case"] for d in get_filter_results(Query(query).test, documents)] == python_hits


@pytest.mark.parametrize("expression", [{"$regex": r"a\0b"}, re.compile(r"a\0b")])
def test_escaped_null_is_valid_regex_syntax(test_db, expression):
    query = {"x": expression}
    documents = [{"x": "a\0b"}, {"x": r"a\0b"}]
    assert get_mongo_results(test_db, query, documents) == documents[:1]
    assert get_filter_results(Query(query).test, documents) == documents[:1]
