"""Per-library matcher entry points, as used by each library's own find path.

Each adapter has `prepare(query) -> object` (the library's construction and
validation step, or the query itself when the library interprets the filter on
every call) and `match(prepared, document) -> bool`. `constructs` says whether
prepare calls the library at all, so a construction timing exists.
"""

from importlib import metadata
import importlib.util
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]


def _mgqpy():
    sys.path.insert(0, str(ROOT / "src"))
    from mgqpy import Query
    sys.path.pop(0)
    return Query, (lambda p, d: p.test(d)), "mgqpy.Query(q).test(d)"


def _mongomock():
    from mongomock.filtering import filter_applies
    return (lambda q: q), (lambda q, d: filter_applies(q, d)), \
        "mongomock.filtering.filter_applies(q, d) (used by Collection.find)"


def _mongoquery():
    from mongoquery import Query
    return Query, (lambda p, d: p.match(d)), "mongoquery.Query(q).match(d)"


def _mongo_query_match():
    # Same top-level module name as mongoquery, so it is installed with
    # `pip install --target "$MQM_TARGET"` and loaded under another name.
    path = Path(os.environ["MQM_TARGET"]) / "mongoquery" / "__init__.py"
    spec = importlib.util.spec_from_file_location("mongo_query_match_fork", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Query, (lambda p, d: p.match(d)), \
        "mongo-query-match: mongoquery.Query(q).match(d) (fork of mongoquery)"


def _montydb(version):
    def load():
        from montydb import configure
        from montydb.engine.queries import QueryFilter
        configure._bson_init(True)
        configure._mongo_compat(version)
        return QueryFilter, (lambda p, d: p(d)), \
            f"montydb.engine.queries.QueryFilter(q)(d), bson on, mongo_version={version}"
    return load


def _tinymongo():
    from tinymongo.table_backends import matches_filter, validate_filter_operators

    def prepare(q):
        validate_filter_operators(q)
        return q
    return prepare, (lambda q, d: matches_filter(d, q)), \
        "tinymongo.table_backends: validate_filter_operators(q); matches_filter(d, q)"


def _mongita():
    from mongita.collection import _doc_matches_slow_filters, _validate_filter

    def prepare(q):
        _validate_filter(q)
        return q
    return prepare, (lambda q, d: _doc_matches_slow_filters(d, q)), \
        "mongita.collection: _validate_filter(q); _doc_matches_slow_filters(d, q) (unindexed find)"


# name: (distribution, loader, constructs)
LIBRARIES = {
    "mgqpy": (None, _mgqpy, True),
    "mongomock": ("mongomock", _mongomock, False),
    "mongoquery": ("mongoquery", _mongoquery, True),
    "mongo-query-match": ("mongo-query-match", _mongo_query_match, True),
    # The default compatibility mode; "4.4" gave identical corpus results.
    "montydb": ("montydb", _montydb("4.2"), True),
    "tinymongo": ("tinymongo", _tinymongo, True),
    "mongita": ("mongita", _mongita, True),
}


def version(name):
    distribution = LIBRARIES[name][0]
    if distribution is None:
        import tomllib
        return tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"] + " (working tree)"
    if distribution == "mongo-query-match":
        found = metadata.distributions(name=distribution, path=[os.environ["MQM_TARGET"]])
        return next(iter(found)).version
    return metadata.version(distribution)
