import copy


def assert_mongo_behavior(test_db, name, input, expected, q):
    __tracebackhide__ = True
    test_db.insert_many(copy.deepcopy(input))
    mongo_expected = test_db.find(q._query, projection={"_id": False})
    assert expected == list(mongo_expected), name


def get_filter_results(match, input):
    __tracebackhide__ = True
    return list(filter(match, input))
