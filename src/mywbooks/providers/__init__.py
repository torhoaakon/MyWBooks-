from __future__ import annotations

import importlib
from enum import StrEnum


# By writing this explicitly, it is earlier for the autocomplete
class Provider(StrEnum):
    ROYALROAD = "royalroad"
    # PATREON = "patreon"
    # WUXIAWORLD = "wuxiaworld"


# fmt: off
_PROVIDER_MODULE: dict[str, str] = {
        Provider.ROYALROAD: "royalroad",
        # Provider.PATREON = "patreon"
        # Provider.WUXIAWORLD = "wuxiaworld"
}
# fmt: on


def get_provider_by_key(key: str):
    try:
        return _PROVIDERS[key]["provider_class"]
    except KeyError:
        raise ValueError(f"No provider registered for {key}")


# ================= Code Gen  =================


def _keypair_for(provider_key: str):
    module_name = _PROVIDER_MODULE[provider_key]

    module = importlib.import_module(f".{module_name}", package=__name__)

    def _get_assert_var(var_name, desc):
        assert hasattr(
            module, var_name
        ), f"Module {provider_key} is missing {var_name} [{desc}]"
        return getattr(module, var_name)

    # key = _get_assert_var("PROVIDER_KEY", "Identification Key")
    short_name = _get_assert_var(
        "PROVIDER_SHORT_NAME", "Short Variable name used to refer to this provider"
    )

    _class = _get_assert_var(
        "f{short_name}Provider", "The Provider class (.i.e. extending Provider)"
    )
    assert isinstance(
        _class, Provider
    ), "Provider class for {provider} is not an instance of provider.base.Provider"

    setattr(_class, "_provider_key", provider_key)

    return (
        provider_key,
        {
            "short_name": short_name,
            "provider_class": _class,
            "module_name": module_name,
        },
    )


_PROVIDERS = dict([_keypair_for(p) for p in _PROVIDER_MODULE.keys()])
