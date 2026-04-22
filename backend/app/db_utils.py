"""
Lightweight database utility helpers with no heavy dependencies.
"""

#: Escape character used in SQL LIKE / ILIKE predicates.
LIKE_ESCAPE_CHAR = "\\"


def escape_like_literal(value: str) -> str:
    """Escape SQL LIKE metacharacters so *value* is matched literally.

    The backslash (the escape character itself) must be escaped first,
    followed by ``%`` and ``_`` wildcards.  The caller is responsible for
    wrapping the result in ``%…%`` and passing ``escape=LIKE_ESCAPE_CHAR``
    to the SQLAlchemy ``ilike()`` / ``like()`` predicate.
    """
    return (
        value
        .replace(LIKE_ESCAPE_CHAR, LIKE_ESCAPE_CHAR * 2)
        .replace("%", f"{LIKE_ESCAPE_CHAR}%")
        .replace("_", f"{LIKE_ESCAPE_CHAR}_")
    )


def prefix_like_pattern(value: str) -> str:
    """Build a LIKE prefix pattern that treats the prefix as a literal string.

    The returned pattern contains backslash escapes produced by
    ``escape_like_literal()``. When using it with SQLAlchemy ``like()`` or
    ``ilike()``, callers must pass ``escape=LIKE_ESCAPE_CHAR`` so the escaping
    is interpreted consistently across databases.
    """
    return f"{escape_like_literal(value)}%"
