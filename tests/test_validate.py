import pytest

from mgqpy import Query


def test_mgqpy_basic_validation():
    Query({"foo": "bar"}).validate()

    with pytest.raises(TypeError):
        Query(None).validate()

    with pytest.raises(TypeError):
        Query([{"foo": "bar"}]).validate()


def test_mgqpy_and_validation():
    Query({"$and": [{"foo": "bar"}]}).validate()

    with pytest.raises(TypeError):
        Query({"$and": "not-a-list"}).validate()

    with pytest.raises(TypeError):
        Query({"$and": [{"foo": "bar"}, "not-a-dict"]}).validate()

    with pytest.raises(TypeError):
        Query(
            {
                "$and": [
                    {"foo": "bar"},
                    {"$and": "not-a-list"},
                ]
            }
        ).validate()


def test_mgqpy_in_nin_validation():
    Query({"foo": {"$in": ["bar", "baz"]}}).validate()

    Query({"foo": {"$nin": ["bar", "baz"]}}).validate()

    with pytest.raises(TypeError):
        Query({"foo": {"$in": "not-a-list"}}).validate()

    with pytest.raises(TypeError):
        Query({"foo": {"$nin": "not-a-list"}}).validate()


# def test_mgqpy_all_validation():
#     Query({"foo": {"$all": ["bar", "baz"]}}).validate()

#     with pytest.raises(TypeError):
#         Query({"foo": {"$all": "not-a-list"}}).validate()

#     with pytest.raises(TypeError):
#         Query({"foo": {"$all": {"foo": "bar"}}}).validate()
