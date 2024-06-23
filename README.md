# mgqpy

[![codecov](https://codecov.io/gh/weiliddat/mgqpy/graph/badge.svg?token=CuQS0w5IkL)](https://codecov.io/gh/weiliddat/mgqpy)

mongo query as a predicate function

```sh
pip install mgqpy
```

```python
from mgqpy import Query

predicate = Query({"foo.bar": 1})

inputs = [
    {"foo": [{"bar": [1]}]},
    {"foo": {"bar": 1}},
    {"foo": None},
]

filtered = filter(predicate.match, inputs)

assert list(filtered) == [
    {"foo": [{"bar": [1]}]},
    {"foo": {"bar": 1}},
]
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
- [ ] \$elemMatch
- [ ] \$size
