"""Tests for Pipeline orchestrator."""

from elsian.pipeline import Pipeline, PipelinePhase
from elsian.context import PipelineContext
from elsian.models.result import PhaseResult


class FakePhase(PipelinePhase):
    def __init__(self, name: str, success: bool = True):
        self._name = name
        self._success = success

    def run(self, context: PipelineContext) -> PhaseResult:
        return PhaseResult(phase_name=self._name, success=self._success, message="ok")


class FailPhase(PipelinePhase):
    def run(self, context: PipelineContext) -> PhaseResult:
        return PhaseResult(phase_name="fail", success=False, message="boom")


def test_pipeline_runs_all_phases():
    p = Pipeline([FakePhase("a"), FakePhase("b"), FakePhase("c")])
    ctx = PipelineContext()
    result = p.run(ctx)
    assert len(result.errors) == 0


def test_pipeline_stops_on_failure():
    p = Pipeline([FakePhase("a"), FailPhase(), FakePhase("c")])
    ctx = PipelineContext()
    result = p.run(ctx)
    assert len(result.errors) == 1
    assert "boom" in result.errors[0]
