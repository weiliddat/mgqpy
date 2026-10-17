import mgqpy


def _match_and(doc, path: str, ov) -> bool:
    for cond in ov:
        if not mgqpy._match_cond(cond, doc):
            return False
    return True


def _match_or(doc, path: str, ov) -> bool:
    for cond in ov:
        if mgqpy._match_cond(cond, doc):
            return True
    return False


def _match_nor(doc, path: str, ov) -> bool:
    for cond in ov:
        if mgqpy._match_cond(cond, doc):
            return False
    return True


def _validate_query_ops(ov) -> bool:
    """
    Validate query op is given a list (shallow).
    Recursion is done by _validate.
    """

    return isinstance(ov, list)
