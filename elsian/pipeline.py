"""Pipeline orchestrator -- lightweight, no business logic."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Callable

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
    """Lightweight orchestrator. Chains phases, manages context. No business logic.

    Stops only when a phase returns ``severity='fatal'``.  Non-fatal results
    (``warning``, ``error``) are logged and preserved but do not interrupt the
    sequence.

    ``on_phase_done`` is an optional observability hook called with the
    PhaseResult immediately after each phase; it carries no business logic.
    """

    def __init__(
        self,
        phases: list[PipelinePhase],
        on_phase_done: Callable[[PhaseResult], None] | None = None,
    ) -> None:
        self.phases = phases
        self._on_phase_done = on_phase_done

    def run(self, context: PipelineContext) -> PipelineContext:
        """Run all phases in sequence. Stops only on fatal severity."""
        for phase in self.phases:
            name = phase.__class__.__name__
            logger.info("Running phase: %s", name)
            _t0 = time.perf_counter()
            result = phase.run(context)
            result.duration_ms = (time.perf_counter() - _t0) * 1000
            context.phase_results.append(result)
            if self._on_phase_done is not None:
                self._on_phase_done(result)
            if result.is_fatal:
                logger.error("Phase %s fatal: %s", name, result.message)
                context.add_error(f"{name}: {result.message}")
                break
            if result.severity in ("warning", "error"):
                logger.warning(
                    "Phase %s %s: %s", name, result.severity, result.message
                )
            else:
                logger.info("Phase %s completed: %s", name, result.message)
        return context
