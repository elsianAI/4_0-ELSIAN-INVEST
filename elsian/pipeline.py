"""Pipeline orchestrator -- lightweight, no business logic."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from elsian.context import PipelineContext
from elsian.models.result import PhaseResult

logger = logging.getLogger(__name__)


class PipelinePhase(ABC):
    """Base for all pipeline phases."""

    @abstractmethod
    def run(self, context: PipelineContext) -> PhaseResult:
        """Execute this phase, mutating context as needed."""
        ...


class Pipeline:
    """Lightweight orchestrator. Chains phases, manages context. No business logic."""

    def __init__(self, phases: list[PipelinePhase]) -> None:
        self.phases = phases

    def run(self, context: PipelineContext) -> PipelineContext:
        """Run all phases in sequence."""
        for phase in self.phases:
            name = phase.__class__.__name__
            logger.info("Running phase: %s", name)
            result = phase.run(context)
            if not result.success:
                logger.error("Phase %s failed: %s", name, result.message)
                context.add_error(f"{name}: {result.message}")
                break
            logger.info("Phase %s completed: %s", name, result.message)
        return context
