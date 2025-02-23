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


def test_mgqpy_or_validation():
    Query({"$or": [{"foo": "bar"}]}).validate()

    with pytest.raises(TypeError):
        Query({"$or": "not-a-list"}).validate()

    with pytest.raises(TypeError):
        Query({"$or": [{"foo": "bar"}, "not-a-dict"]}).validate()

    with pytest.raises(TypeError):
        Query(
            {
                "$or": [
                    {"foo": "bar"},
                    {"$or": "not-a-list"},
                ]
            }
        ).validate()


def test_mgqpy_nor_validation():
    Query({"$nor": [{"foo": "bar"}]}).validate()

    with pytest.raises(TypeError):
        Query({"$nor": "not-a-list"}).validate()

    with pytest.raises(TypeError):
        Query({"$nor": [{"foo": "bar"}, "not-a-dict"]}).validate()

    with pytest.raises(TypeError):
        Query(
            {
                "$nor": [
                    {"foo": "bar"},
                    {"$nor": "not-a-list"},
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


def test_mgqpy_all_validation():
    Query({"foo": {"$all": ["bar", "baz"]}}).validate()

    Query({"foo": {"$all": []}}).validate()

    Query({"foo": {"$all": [{"$elemMatch": {"bar": "baz"}}]}}).validate()

    with pytest.raises(TypeError):
        Query({"foo": {"$all": "not-a-list"}}).validate()

    with pytest.raises(TypeError):
        Query({"foo": {"$all": {"foo": "bar"}}}).validate()

    with pytest.raises(TypeError):
        Query({"foo": {"$all": [{"$and": "not-allowed"}]}}).validate()


def test_mgqpy_mod_validation():
    Query({"foo": {"$mod": [5, 1]}}).validate()

    with pytest.raises(TypeError):
        Query({"foo": {"$mod": "not-a-list"}}).validate()

    with pytest.raises(TypeError):
        Query({"foo": {"$mod": ["a", "b"]}}).validate()


def test_mgqpy_size_validation():
    Query({"foo": {"$size": 2}}).validate()

    with pytest.raises(TypeError):
        Query({"foo": {"$size": "2"}}).validate()

    with pytest.raises(TypeError):
        Query({"foo": {"$size": ["a", "b"]}}).validate()
