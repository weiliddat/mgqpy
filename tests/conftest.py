import os
from uuid import uuid4

from pymongo import MongoClient
import pytest


@pytest.fixture(scope="session")
def mongo_db():
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    with MongoClient(os.environ.get("MONGODB_URI", "mongodb://127.0.0.1:27017")) as client:
        db = client[f"mgqpy_test_{worker}_{uuid4().hex}"]
        try:
            yield db
        finally:
            client.drop_database(db.name)


@pytest.fixture
def test_db(mongo_db):
    collection = mongo_db[f"case_{uuid4().hex}"]
    try:
        yield collection
    finally:
        collection.drop()
