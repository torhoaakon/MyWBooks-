from __future__ import annotations

import importlib
import typing

from ..models import ProviderKey
from .base import Provider

## === Warning!! ===
# When adding new providers. Both
#   - A unique identifier most be added to the ProviderKey class in
#           `models.py`, and
#   - The module name most be added to the _PROVIDER_MODULES dict


# fmt: off
_PROVIDER_MODULES: dict[str, str] = {
        ProviderKey.ROYALROAD: "royalroad",
        # Provider.PATREON = "patreon"
        # Provider.WUXIAWORLD = "wuxiaworld"
}
# fmt: on


class _ProviderInfo(typing.NamedTuple):
    provider_key: str
    module_name: str
    short_name: str
    provider_class: Provider


def get_provider_by_key(key: str) -> Provider:
    # Store provider_register as function attribute
    if not hasattr(get_provider_by_key, "initialized_value"):
        setattr(
            get_provider_by_key,
            "provider_register",
            {},
        )
    provider_register: dict[str, _ProviderInfo] = getattr(
        get_provider_by_key, "provider_register"
    )

    # Check for provider in registry
    pinfo = provider_register.get(key)
    if pinfo:
        return pinfo.provider_class

    # If not loaded, look up module name
    mname = _PROVIDER_MODULES.get(key)
    if not mname:
        raise ValueError(f"No provider registered for {key}")

    # Load module
    print("Loading provider module for '{key}', at  '{mname}'")

    module = importlib.import_module(f".{mname}", package=__name__)

    def _get_assert_var(var_name: str, desc: str) -> typing.Any:
        if not hasattr(module, var_name):
            raise RuntimeError(f"Module {key} is missing {var_name} [{desc}]")
        return getattr(module, var_name)

    # key = _get_assert_var("PROVIDER_KEY", "Identification Key")
    short_name: str = _get_assert_var(
        "PROVIDER_SHORT_NAME", "Short Variable name used to refer to this provider"
    )

    _class: Provider = _get_assert_var(
        "f{short_name}Provider", "The Provider class (.i.e. extending Provider)"
    )
    assert isinstance(
        _class, ProviderKey
    ), "Provider class for {provider} is not an instance of provider.base.Provider"

    # Set _provider_key attribute of Provider class
    setattr(_class, "_provider_key", key)

    provider_register[key] = _ProviderInfo(
        provider_key=key,
        module_name=mname,
        short_name=short_name,
        provider_class=_class,
    )

    return _class


__all__ = ["Provider", "get_provider_by_key"]
