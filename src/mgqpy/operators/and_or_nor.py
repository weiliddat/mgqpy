import mgqpy


def _match_and(doc, path: str, ov) -> bool:
    if not _validate_query_ops(ov):
        return False

    return all(mgqpy._match_cond(cond, doc) for cond in ov)


def _match_or(doc, path: str, ov) -> bool:
    if not _validate_query_ops(ov):
        return False

    return any(mgqpy._match_cond(cond, doc) for cond in ov)


def _match_nor(doc, path: str, ov) -> bool:
    if not _validate_query_ops(ov):
        return False

    return not any(mgqpy._match_cond(cond, doc) for cond in ov)


def _validate_query_ops(ov) -> bool:
    """
    Validate query op is given a list (shallow).
    Recursion is done by _validate and _match_cond.
    """

    return isinstance(ov, list)
