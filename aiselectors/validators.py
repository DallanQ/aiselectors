def require_href(elements):
    return all(elm.get("href") for elm in elements)


def require_unique(elements):
    return len(elements) == 1


def require_unique_href(elements):
    # return True if there is one element or all elements have the same href attribute
    return len(elements) == 1 or len({elm.get("href") for elm in elements}) == 1
