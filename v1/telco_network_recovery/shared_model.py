from relationalai.semantics import Model
from types import SimpleNamespace as _SimpleNamespace
from typing import Protocol as _Protocol, cast as _cast


class SharedModel(_Protocol):
    pass


def build_shared(m: Model) -> SharedModel:
    _cached = getattr(m, '__build_shared', None)
    if _cached is not None:
        return _cached

    _shared = _cast(SharedModel, _SimpleNamespace())
    object.__setattr__(m, '__build_shared', _shared)
    return _shared
