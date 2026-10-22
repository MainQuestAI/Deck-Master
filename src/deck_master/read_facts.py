"""Explicit per-response immutable object facts, never write eligibility.

Create inside a read entrypoint and discard on return. No global/ContextVar
state: mutation entrypoints always construct their own real Store and recheck.
"""
from .models import validate_ref


class ReadFacts:
    def __init__(self, store, document):
        self.store, self.document = store, document
        self.objects = {}

    def read_object_json(self, ref):
        validate_ref(ref, where='object')
        key = (ref['path'], ref['sha256'])
        if key not in self.objects:
            self.objects[key] = self.store.read_object_json(ref)
        return self.objects[key]

    def __getattr__(self, name):
        return getattr(self.store, name)
