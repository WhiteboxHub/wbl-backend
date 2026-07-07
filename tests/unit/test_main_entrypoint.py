from importlib import import_module


def test_root_main_module_exposes_fastapi_app():
    module = import_module("main")
    assert hasattr(module, "app")
