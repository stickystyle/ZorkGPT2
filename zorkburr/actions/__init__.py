"""Actions package. Patches Burr-decorated functions with a .run() test helper."""
import functools
from burr.core import action as _burr_action


class _ActionDecorator:
    """Wraps burr.core.action to add a .run() method for testing."""

    def __init__(self, reads, writes, tags=None):
        self._burr_action = _burr_action(reads=reads, writes=writes, tags=tags or [])

    def __call__(self, fn):
        wrapped = self._burr_action(fn)

        # Attach .run() so tests can call action.run(state, **inputs)
        @functools.wraps(fn)
        def run(state, **inputs):
            return fn(state, **inputs)

        wrapped.run = run
        return wrapped


def action(reads, writes, tags=None):
    """Drop-in replacement for burr.core.action that adds .run() for testing."""
    return _ActionDecorator(reads=reads, writes=writes, tags=tags)
