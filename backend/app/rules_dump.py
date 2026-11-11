"""Stable dumps of rulesets across versions (COL-11, v0.11)."""

from pydantic import model_serializer


def omit_unset_extensions(*names):
    """Serializer dropping later-version fields left empty: rulesets pinned before them (v0.10
    and older) dump, and so fingerprint, exactly as when they were pinned."""

    def serialize(self, handler):
        data = handler(self)
        for name in names:
            if name in data and data[name] in (None, {}, []):
                data.pop(name)
        return data

    return model_serializer(mode="wrap")(serialize)
