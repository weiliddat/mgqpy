"""Compose already-compiled document predicates."""


def conjunction(predicates):
    if len(predicates) == 1:
        return predicates[0]

    def match(doc):
        for predicate in predicates:
            if not predicate(doc):
                return False
        return True
    return match


def disjunction(predicates):
    def match(doc):
        for predicate in predicates:
            if predicate(doc):
                return True
        return False
    return match


def negate(predicate):
    def match(doc):
        return not predicate(doc)
    return match
