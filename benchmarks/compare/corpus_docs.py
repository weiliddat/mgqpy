"""Independent query set: examples from the MongoDB manual, with their sample documents.

Each group is one manual page's sample collection and the filters shown on that
page, transcribed into Python. Expected results come from the servers, not from
the page text. Projections, limits and `$type` filters on unrelated fields are
dropped; the `$type` and `$exists` pages use the large `sample_mflix` dataset,
so those groups use small stand-in documents with the same field shapes, and
the `$all` page's sample documents are transcribed from the page's examples.
Shell-only spellings (`/pattern/` literals) become compiled Python patterns.
"""

import re

BASE = "https://www.mongodb.com/docs/manual/"

INVENTORY = [
    {"item": "journal", "qty": 25, "size": {"h": 14, "w": 21, "uom": "cm"}, "status": "A"},
    {"item": "notebook", "qty": 50, "size": {"h": 8.5, "w": 11, "uom": "in"}, "status": "A"},
    {"item": "paper", "qty": 100, "size": {"h": 8.5, "w": 11, "uom": "in"}, "status": "D"},
    {"item": "planner", "qty": 75, "size": {"h": 22.85, "w": 30, "uom": "cm"}, "status": "D"},
    {"item": "postcard", "qty": 45, "size": {"h": 10, "w": 15.25, "uom": "cm"}, "status": "A"},
]

ARRAYS = [
    {"item": "journal", "qty": 25, "tags": ["blank", "red"], "dim_cm": [14, 21]},
    {"item": "notebook", "qty": 50, "tags": ["red", "blank"], "dim_cm": [14, 21]},
    {"item": "paper", "qty": 100, "tags": ["red", "blank", "plain"], "dim_cm": [14, 21]},
    {"item": "planner", "qty": 75, "tags": ["blank", "red"], "dim_cm": [22.85, 30]},
    {"item": "postcard", "qty": 45, "tags": ["blue"], "dim_cm": [10, 15.25]},
]

INSTOCK = [
    {"item": "journal", "instock": [{"warehouse": "A", "qty": 5}, {"warehouse": "C", "qty": 15}]},
    {"item": "notebook", "instock": [{"warehouse": "C", "qty": 5}]},
    {"item": "paper", "instock": [{"warehouse": "A", "qty": 60}, {"warehouse": "B", "qty": 15}]},
    {"item": "planner", "instock": [{"warehouse": "A", "qty": 40}, {"warehouse": "B", "qty": 5}]},
    {"item": "postcard", "instock": [{"warehouse": "B", "qty": 15}, {"warehouse": "C", "qty": 35}]},
]

SURVEY = [
    {"results": [{"product": "abc", "score": 10}, {"product": "xyz", "score": 5}]},
    {"results": [{"product": "abc", "score": 8}, {"product": "xyz", "score": 7}]},
    {"results": [{"product": "abc", "score": 7}, {"product": "xyz", "score": 8}]},
    {"results": [{"product": "abc", "score": 7}, {"product": "def", "score": 8}]},
    {"results": {"product": "xyz", "score": 7}},
]

ALL_INVENTORY = [
    {"code": "xyz", "tags": ["school", "book", "bag", "headphone", "appliance"],
     "qty": [{"size": "S", "num": 10, "color": "blue"}, {"size": "M", "num": 45, "color": "blue"},
             {"size": "L", "num": 100, "color": "green"}]},
    {"code": "abc", "tags": ["appliance", "school", "book"],
     "qty": [{"size": "6", "num": 100, "color": "green"}, {"size": "6", "num": 50, "color": "blue"},
             {"size": "8", "num": 100, "color": "brown"}]},
    {"code": "efg", "tags": ["school", "book"],
     "qty": [{"size": "S", "num": 10, "color": "blue"}, {"size": "M", "num": 100, "color": "blue"},
             {"size": "L", "num": 100, "color": "green"}]},
    {"code": "ijk", "tags": ["electronics", "school"],
     "qty": [{"size": "M", "num": 100, "color": "green"}]},
]

PRODUCTS = [
    {"sku": "abc123", "description": "Single line description."},
    {"sku": "abc789", "description": "First line\nSecond line"},
    {"sku": "xyz456", "description": "Many spaces before     line"},
    {"sku": "xyz789", "description": "Multiple\nline description"},
    {"sku": "Abc789", "description": "SKU starts with A"},
]

GROUPS = [
    ("Query documents", "tutorial/query-documents/", INVENTORY, [
        {}, {"status": "D"}, {"status": {"$in": ["A", "D"]}}, {"status": "A", "qty": {"$lt": 30}},
        {"$or": [{"status": "A"}, {"qty": {"$lt": 30}}]},
        {"status": "A", "$or": [{"qty": {"$lt": 30}}, {"item": {"$regex": "^p"}}]},
    ]),
    ("Query embedded documents", "tutorial/query-embedded-documents/", INVENTORY, [
        {"size": {"h": 14, "w": 21, "uom": "cm"}}, {"size": {"w": 21, "h": 14, "uom": "cm"}},
        {"size.uom": "in"}, {"size.h": {"$lt": 15}},
        {"size.h": {"$lt": 15}, "size.uom": "in", "status": "D"},
    ]),
    ("Query an array", "tutorial/query-arrays/", ARRAYS, [
        {"tags": ["red", "blank"]}, {"tags": {"$all": ["red", "blank"]}}, {"tags": "red"},
        {"dim_cm": {"$gt": 25}}, {"dim_cm": {"$gt": 15, "$lt": 20}},
        {"dim_cm": {"$elemMatch": {"$gt": 22, "$lt": 30}}}, {"dim_cm.1": {"$gt": 25}},
        {"tags": {"$size": 3}},
        # $regex and $not page examples, which use the same item names.
        {"item": {"$not": re.compile("^p.*")}}, {"item": {"$not": {"$regex": "^p.*"}}},
        {"item": {"$not": {"$regex": re.compile("^p.*")}}},
    ]),
    ("Query an array of embedded documents", "tutorial/query-array-of-documents/", INSTOCK, [
        {"instock": {"warehouse": "A", "qty": 5}}, {"instock": {"qty": 5, "warehouse": "A"}},
        {"instock.qty": {"$lte": 20}}, {"instock.0.qty": {"$lte": 20}},
        {"instock": {"$elemMatch": {"qty": 5, "warehouse": "A"}}},
        {"instock": {"$elemMatch": {"qty": {"$gt": 10, "$lte": 20}}}},
        {"instock.qty": {"$gt": 10, "$lte": 20}}, {"instock.qty": 5, "instock.warehouse": "A"},
    ]),
    ("Query for null or missing fields", "tutorial/query-for-null-fields/", [{"item": None}, {}], [
        {"item": None}, {"item": {"$ne": None}}, {"item": {"$type": 10}}, {"item": {"$exists": False}},
    ]),
    ("$elemMatch", "reference/operator/query/elemMatch/",
     [{"results": [82, 85, 88]}, {"results": [75, 88, 89]}] + SURVEY, [
        {"results": {"$elemMatch": {"$gte": 80, "$lt": 85}}},
        {"results": {"$elemMatch": {"product": "xyz", "score": {"$gte": 8}}}},
        {"results": {"$elemMatch": {"product": "xyz"}}}, {"results.product": "xyz"},
        {"results": {"$elemMatch": {"product": {"$ne": "xyz"}}}}, {"results.product": {"$ne": "xyz"}},
    ]),
    ("$all", "reference/operator/query/all/", ALL_INVENTORY, [
        {"tags": {"$all": ["appliance", "school", "book"]}},
        {"qty": {"$all": [{"$elemMatch": {"size": "M", "num": {"$gt": 50}}},
                          {"$elemMatch": {"num": 100, "color": "green"}}]}},
        {"qty.num": {"$all": [50]}}, {"qty.num": 50}, {"tags": {"$all": [["ssl", "security"]]}},
        {"tags": {"$all": []}},
    ]),
    ("$mod", "reference/operator/query/mod/",
     [{"item": "abc123", "qty": 0}, {"item": "xyz123", "qty": 5}, {"item": "ijk123", "qty": 12}], [
        {"qty": {"$mod": [4, 0]}}, {"qty": {"$mod": [4.0, 0]}}, {"qty": {"$mod": [4.5, 0]}},
        {"qty": {"$mod": [4.99, 0]}}, {"qty": {"$mod": [-4, -0]}},
    ]),
    ("$nin", "reference/operator/query/nin/", [
        {"item": "Pens", "quantity": 350, "tags": ["school", "office"]},
        {"item": "Erasers", "quantity": 15, "tags": ["school", "home"]},
        {"item": "Maps", "tags": ["office", "storage"]},
        {"item": "Books", "quantity": 5, "tags": ["school", "storage", "home"]},
    ], [
        {"quantity": {"$nin": [5, 15]}}, {"tags": {"$nin": ["school"]}},
    ]),
    ("$exists (stand-in documents)", "reference/operator/query/exists/",
     [{"title": "a", "rated": "TV-G"}, {"title": "b", "rated": "R"}, {"title": "c", "rated": None},
      {"title": "d"}, {"title": "e", "metacritic": 61}], [
        {"rated": {"$exists": True, "$nin": ["R", "PG-13"]}}, {"rated": {"$exists": True}},
        {"rated": {"$exists": False}}, {"metacritic": {"$exists": True}}, {"metacritic": {"$ne": None}},
    ]),
    ("$type (stand-in documents)", "reference/operator/query/type/",
     [{"imdb": {"rating": 7.1}, "genres": ["Drama"], "year": 2013},
      {"imdb": {"rating": ""}, "genres": ["Short"], "year": 2013},
      {"imdb": {"rating": 6}, "genres": "Comedy", "year": 2012}], [
        {"imdb.rating": {"$type": 2}, "year": 2013}, {"imdb.rating": {"$type": "string"}, "year": 2013},
        {"imdb.rating": {"$type": "number"}}, {"imdb.rating": {"$type": [2, 1]}},
        {"imdb.rating": {"$type": ["string", "double"]}}, {"genres": {"$type": "array"}},
    ]),
    ("$regex", "reference/operator/query/regex/", PRODUCTS, [
        {"sku": {"$regex": re.compile("789$")}}, {"sku": {"$regex": re.compile("^ABC", re.I)}},
        {"description": {"$regex": re.compile(r"\bline\b")}},
        {"description": {"$regex": "^S", "$options": "m"}}, {"description": {"$regex": re.compile("^S")}},
        {"description": {"$regex": re.compile("S")}},
        {"description": {"$regex": "m.*line", "$options": "si"}},
        {"sku": {"$regex": "abc #category code\n123 #item number", "$options": "x"}},
        {"sku": {"$regex": "(?i)a(?-i)bc"}},
        {"sku": {"$regex": re.compile("acme.*corp", re.I), "$nin": ["acmeblahcorp"]}},
    ]),
]


def groups():
    """[(label, url, documents, queries)]"""
    return [(label, BASE + path, docs, queries) for label, path, docs, queries in GROUPS]
