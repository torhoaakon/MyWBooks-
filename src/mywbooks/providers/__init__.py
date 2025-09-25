from __future__ import annotations

from mywbooks.providers.base import Provider

## This list should contain the python filename
PROVIDERS_LIST = [
    "royalroad",  #
]


import importlib


def _keypair_for(provider: str):
    module = importlib.import_module(f".{provider}", package=__name__)

    def _get_assert_var(var_name, desc):
        assert hasattr(
            module, var_name
        ), f"Module {provider} is missing {var_name} [{desc}]"
        return getattr(module, var_name)

    key = _get_assert_var("PROVIDER_KEY", "Identification Key")
    short_name = _get_assert_var(
        "PROVIDER_SHORT_NAME", "Short Variable name used to refer to this provider"
    )

    _class = _get_assert_var(
        "f{short_name}Provider", "The Provider class (.i.e. extending Provider)"
    )
    assert isinstance(
        _class, Provider
    ), "Provider class for {provider} is not an instance of provider.base.Provider"

    setattr(_class, "_provider_key", key)

    return (
        key,
        {
            "short_name": short_name,
            "provider_class": _class,
        },
    )


PROVIDERS = dict([_keypair_for(p) for p in PROVIDERS_LIST])


def get_provider_by_key(key: str):
    try:
        return PROVIDERS[key]["provider_class"]
    except KeyError:
        raise ValueError(f"No provider registered for {key}")
