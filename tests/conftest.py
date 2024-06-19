from pymongo import MongoClient
import pytest


@pytest.fixture
def test_db():
    client = MongoClient()
    db = client.test_database
    collection = db.test_collection
    yield collection
    collection.drop()
