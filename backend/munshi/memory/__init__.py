# Munshi - Memory module
# Hindsight integration for long-term customer memory
#
# Modules are imported lazily to avoid pulling in sqlmodel/hindsight_client
# at import time when running unit tests without those deps.

__all__ = ["client", "bank_setup", "events", "queries", "parsing", "outbox"]


def __getattr__(name):
    if name in __all__:
        import importlib
        module = importlib.import_module(f"munshi.memory.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
