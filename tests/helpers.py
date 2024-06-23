import copy


def get_mongo_results(test_db, input, q):
    __tracebackhide__ = True
    test_db.insert_many(copy.deepcopy(input))
    mongo_expected = test_db.find(q._query, projection={"_id": False})
    return list(mongo_expected)


def get_filter_results(match, input):
    __tracebackhide__ = True
    return list(filter(match, input))
