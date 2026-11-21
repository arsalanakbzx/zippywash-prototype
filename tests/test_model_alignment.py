"""Reflection tests: the code implements exactly the final Milestone 5 model."""
import dataclasses
import importlib
import inspect
import pkgutil
from pathlib import Path

import pytest

import zippywash
import zippywash.customer_order_service as cos
import zippywash.operations_resource as ops
from tests.model_spec import COLLECTIONS, MODEL, to_snake


def domain_classes():
    found = {}
    for pkg in (cos, ops):
        for m in pkgutil.iter_modules(pkg.__path__):
            module = importlib.import_module(f"{pkg.__name__}.{m.name}")
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if obj.__module__ == module.__name__ and dataclasses.is_dataclass(obj) and hasattr(obj, "_pk"):
                    found[name] = obj
    return found


CLASSES = domain_classes()


def test_exactly_the_25_final_domain_classes():
    assert len(MODEL) == 25
    assert set(CLASSES) == set(MODEL)


def test_removed_concepts_are_gone():
    root = Path(zippywash.__file__).parent
    assert not (root / "person.py").exists()
    source = "\n".join(p.read_text() for p in root.rglob("*.py")) + (root / "database" / "schema.sql").read_text()
    for removed in ("class Person", "selected_add_ons", "AddOnType", "order_item_add_ons", "SupplyOrder"):
        assert removed not in source
    for cls in CLASSES.values():
        assert all(base.__name__ != "Person" for base in cls.__mro__)


@pytest.mark.parametrize("name", sorted(MODEL))
def test_every_attribute_is_present(name):
    attrs, _, _ = MODEL[name]
    fields = {f.name: f for f in dataclasses.fields(CLASSES[name])}
    for a in attrs:
        assert to_snake(a) in fields, f"{name}.{a} missing"


@pytest.mark.parametrize("name", sorted(MODEL))
def test_collections_are_typed_lists_not_shared(name):
    cls = CLASSES[name]
    fields = {f.name: f for f in dataclasses.fields(cls)}
    for a in COLLECTIONS.get(name, []):
        f = fields[to_snake(a)]
        assert f.default_factory is list, f"{name}.{a} must default to a new list"


@pytest.mark.parametrize("name", sorted(MODEL))
def test_every_method_with_its_parameters(name):
    _, methods, statics = MODEL[name]
    cls = CLASSES[name]
    for method, params in methods.items():
        attr = inspect.getattr_static(cls, to_snake(method), None)
        assert attr is not None, f"{name}.{method} missing"
        is_static = isinstance(attr, staticmethod)
        assert is_static == (method in statics), f"{name}.{method} static mismatch"
        fn = attr.__func__ if is_static else attr
        names = [p for p in inspect.signature(fn).parameters if p != "self"]
        assert names == [to_snake(p) for p in params], f"{name}.{method}{tuple(names)}"


def test_no_stub_bodies_in_domain_or_services():
    root = Path(zippywash.__file__).parent
    for path in root.rglob("*.py"):
        text = path.read_text()
        for word in ("NotImplementedError", "TODO", "    pass\n"):
            assert word not in text, f"{word.strip()} in {path.name}"
