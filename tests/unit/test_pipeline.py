"""Tests for Pipeline orchestrator and PhaseResult severity model (BL-063)."""

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


class WarnPhase(PipelinePhase):
    def run(self, context: PipelineContext) -> PhaseResult:
        return PhaseResult(
            phase_name="warn", success=True, severity="warning", message="meh"
        )


class ExplicitFatalPhase(PipelinePhase):
    def run(self, context: PipelineContext) -> PhaseResult:
        return PhaseResult(phase_name="fatal", severity="fatal", message="hard stop")


# ── Existing behaviour (preserved) ────────────────────────────────────

def test_pipeline_runs_all_phases():
    p = Pipeline([FakePhase("a"), FakePhase("b"), FakePhase("c")])
    ctx = PipelineContext()
    result = p.run(ctx)
    assert len(result.errors) == 0


def test_pipeline_stops_on_failure():
    """success=False ⇒ severity promoted to fatal ⇒ pipeline stops."""
    p = Pipeline([FakePhase("a"), FailPhase(), FakePhase("c")])
    ctx = PipelineContext()
    result = p.run(ctx)
    assert len(result.errors) == 1
    assert "boom" in result.errors[0]


# ── New severity semantics (BL-063) ───────────────────────────────────

def test_pipeline_continues_on_warning():
    """A warning phase must NOT stop the pipeline."""
    ran: list[str] = []

    class TrackPhase(PipelinePhase):
        def run(self, ctx: PipelineContext) -> PhaseResult:
            ran.append("after")
            return PhaseResult(phase_name="after", success=True, message="ok")

    p = Pipeline([FakePhase("a"), WarnPhase(), TrackPhase()])
    ctx = PipelineContext()
    p.run(ctx)
    assert "after" in ran
    assert len(ctx.errors) == 0  # warnings do not populate errors


def test_pipeline_stops_on_explicit_fatal():
    """An explicit severity='fatal' must halt the pipeline."""
    ran: list[str] = []

    class AfterPhase(PipelinePhase):
        def run(self, ctx: PipelineContext) -> PhaseResult:
            ran.append("after")
            return PhaseResult(phase_name="after", success=True)

    p = Pipeline([ExplicitFatalPhase(), AfterPhase()])
    ctx = PipelineContext()
    p.run(ctx)
    assert "after" not in ran
    assert len(ctx.errors) == 1


def test_pipeline_accumulates_phase_results():
    """context.phase_results must contain one entry per phase run."""
    p = Pipeline([FakePhase("a"), FakePhase("b"), FakePhase("c")])
    ctx = PipelineContext()
    p.run(ctx)
    assert len(ctx.phase_results) == 3
    assert ctx.phase_results[0].phase_name == "a"
    assert ctx.phase_results[2].phase_name == "c"


def test_pipeline_accumulates_until_fatal():
    """phase_results must contain entries up to and including the fatal phase."""
    p = Pipeline([FakePhase("a"), ExplicitFatalPhase(), FakePhase("c")])
    ctx = PipelineContext()
    p.run(ctx)
    assert len(ctx.phase_results) == 2
    assert ctx.phase_results[1].phase_name == "fatal"


def test_on_phase_done_called_for_each_phase():
    """on_phase_done callback must fire once per phase run."""
    seen: list[str] = []

    def _cb(result: PhaseResult) -> None:
        seen.append(result.phase_name)

    p = Pipeline([FakePhase("x"), WarnPhase(), FakePhase("z")], on_phase_done=_cb)
    ctx = PipelineContext()
    p.run(ctx)
    assert seen == ["x", "warn", "z"]


def test_on_phase_done_called_for_fatal_before_stopping():
    """on_phase_done must be called for the fatal phase before the pipeline stops."""
    seen: list[str] = []

    def _cb(result: PhaseResult) -> None:
        seen.append(result.phase_name)

    p = Pipeline([FakePhase("a"), ExplicitFatalPhase(), FakePhase("c")], on_phase_done=_cb)
    ctx = PipelineContext()
    p.run(ctx)
    assert seen == ["a", "fatal"]


# ── PhaseResult backward compatibility ───────────────────────────────

def test_phase_result_backward_compat_success_false_becomes_fatal():
    """success=False with no explicit severity must silently promote to fatal."""
    r = PhaseResult(success=False, message="old api")
    assert r.severity == "fatal"
    assert r.is_fatal


def test_phase_result_success_true_is_ok_by_default():
    r = PhaseResult(success=True, message="fine")
    assert r.severity == "ok"
    assert not r.is_fatal


def test_phase_result_warning_not_fatal():
    r = PhaseResult(success=True, severity="warning", message="degraded")
    assert not r.is_fatal


def test_phase_result_explicit_fatal_is_fatal():
    r = PhaseResult(severity="fatal", message="gone")
    assert r.is_fatal
