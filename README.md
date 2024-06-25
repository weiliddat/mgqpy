# mgqpy

[![codecov](https://codecov.io/gh/weiliddat/mgqpy/graph/badge.svg?token=CuQS0w5IkL)](https://codecov.io/gh/weiliddat/mgqpy)

[MongoDB query](https://www.mongodb.com/docs/manual/reference/operator/query/) as a predicate function

This aims to be consistent with how MongoDB's matches documents. This includes traversal across nested dicts and lists, None and field-presence/absence handling.

## Installation

```sh
pip install mgqpy
```

## Usage

Test if an input matches the query.

Invalid queries (e.g. using $and without a list) will automatically return False.

Use the `validate` method to raise errors if there's a problem with the query.

```python
from mgqpy import Query

predicate = Query({"foo.bar": {"$gt": 1}})

inputs = [
    {"foo": [{"bar": [1, 2]}]},
    {"foo": {"bar": 1}},
    {"foo": {"bar": 2}},
    {"foo": None},
]

filtered = filter(predicate.match, inputs)

assert list(filtered) == [
    {"foo": [{"bar": [1, 2]}]},
    {"foo": {"bar": 2}},
]
```

Use `validate` to validate queries given.

```python
predicate = Query({"foo": {"$in": 1}})

try:
    predicate.validate()
except TypeError as e:
    # ...
```

`validate` returns the `Query` instance so you can chain `match` if you wish to validate and test against an input in one go.

```python
predicate.validate().match({"foo": 1})
```

## Supported operators

Comparison query operators

- [x] \$eq
- [x] \$eq (implicit), e.g. `{"foo": None}`
- [x] \$ne
- [x] \$gt
- [x] \$gte
- [x] \$lt
- [x] \$lte
- [x] \$in
- [x] \$nin

Logical query operators

- [x] \$and
- [x] \$and (implicit), e.g. `{"foo": 1, "bar": "baz"}`
- [x] \$or
- [x] \$not
- [x] \$nor

Evaluation query operators

- [x] \$regex
- [x] \$regex (implicit), e.g. `{"foo": re.compile('^bar')}`
- [x] \$mod

Array query operators

- [x] \$all
- [x] \$elemMatch
- [x] \$size
