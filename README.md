# mgqpy

mongo query as a python filter predicate

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
- [ ] \$ne
- [x] \$gt
- [x] \$gte
- [ ] \$lt
- [ ] \$lte
- [ ] \$in
- [ ] \$nin

Logical query operators

- [ ] \$and
- [x] \$and (implicit), e.g. `{"foo": 1, "bar": "baz"}`
- [ ] \$or
- [ ] \$not
- [ ] \$nor

Evaluation query operators

- [ ] \$regex
- [ ] \$mod

Array query operators

- [ ] \$all
- [ ] \$elemMatch
- [ ] \$size
