from integrations.mcp.base_client import ContextProvider


class ContextProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, ContextProvider] = {}

    def register(self, provider: ContextProvider, *, replace: bool = False) -> None:
        if provider.name in self._providers and not replace:
            raise ValueError(f"이미 등록된 Context Provider입니다: {provider.name}")
        self._providers[provider.name] = provider

    def get(self, name: str) -> ContextProvider:
        try:
            return self._providers[name]
        except KeyError as exc:
            raise LookupError(f"등록되지 않은 Context Provider입니다: {name}") from exc

    def status(self) -> dict[str, bool]:
        return {
            name: bool(getattr(provider, "implemented", False))
            for name, provider in sorted(self._providers.items())
        }


def build_default_context_registry() -> ContextProviderRegistry:
    from integrations.mcp.congestion_client import CongestionMCPProvider
    from integrations.mcp.weather_client import WeatherMCPProvider

    registry = ContextProviderRegistry()
    registry.register(WeatherMCPProvider())
    registry.register(CongestionMCPProvider())
    return registry


__all__ = ["ContextProviderRegistry", "build_default_context_registry"]

