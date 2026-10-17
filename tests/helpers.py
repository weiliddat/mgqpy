import copy

from mgqpy import Query


def assert_matches(test_db, query, documents, hits):
    """Check independent expected document IDs in Python and on the real server."""
    __tracebackhide__ = True
    predicate = Query(query)
    assert [i for i, doc in enumerate(documents) if predicate.test(doc)] == hits
    test_db.insert_many([dict(doc, _id=i) for i, doc in enumerate(documents)])
    assert [doc["_id"] for doc in test_db.find(query, {"_id": 1}).sort("_id", 1)] == hits


def get_mongo_results(test_db, query, input):
    __tracebackhide__ = True
    test_db.insert_many(copy.deepcopy(input))
    mongo_expected = test_db.find(query, projection={"_id": False})
    return list(mongo_expected)


def get_filter_results(match, input):
    __tracebackhide__ = True
    return list(filter(match, input))
