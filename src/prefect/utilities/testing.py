""""
Internal utilities for tests.
"""
import os
import sys
from contextlib import contextmanager

import prefect.context
import prefect.settings


def exceptions_equal(a, b):
    """
    Exceptions cannot be compared by `==`. They can be compared using `is` but this
    will fail if the exception is serialized/deserialized so this utility does its
    best to assert equality using the type and args used to initialize the exception
    """
    if a == b:
        return True
    return type(a) == type(b) and getattr(a, "args", None) == getattr(b, "args", None)


# AsyncMock has a new import path in Python 3.8+

if sys.version_info < (3, 8):
    # https://docs.python.org/3/library/unittest.mock.html#unittest.mock.AsyncMock
    from mock import AsyncMock
else:
    from unittest.mock import AsyncMock


@contextmanager
def temporary_settings(**kwargs):
    """
    Temporarily override setting values by updating the current os.environ and changing
    the profile context.

    This will _not_ mutate values that have been already been accessed at module
    load time.

    This function should only be used for testing.

    Example:
        >>> import prefect.settings
        >>> with temporary_settings(PREFECT_API_URL="foo"):
        >>>    assert prefect.settings.from_context().api_url == "foo"
        >>>    assert prefect.settings.from_context().api_url == "foo"
        >>> assert prefect.settings.from_context().api_url is None
    """
    old_env = os.environ.copy()

    # Cast to strings
    variables = {key: str(value) for key, value in kwargs.items()}

    try:
        for key in variables:
            os.environ[key] = str(variables[key])

        new_settings = prefect.settings.from_env()

        with prefect.context.ProfileContext(
            name="temporary", settings=new_settings, env=variables
        ):
            yield new_settings

    finally:
        for key in variables:
            if old_env.get(key):
                os.environ[key] = old_env[key]
            else:
                os.environ.pop(key, None)
