"""프로세스 수명 동안 공유하는 Registry와 application service."""

from application.recommendation.orchestrator import RecommendationOrchestrator
from domains.common.registry import build_default_domain_registry
from integrations.mcp.registry import build_default_context_registry

domain_registry = build_default_domain_registry()
context_registry = build_default_context_registry()
recommendation_orchestrator = RecommendationOrchestrator(
    domain_registry=domain_registry,
    context_registry=context_registry,
)

__all__ = ["domain_registry", "context_registry", "recommendation_orchestrator"]

