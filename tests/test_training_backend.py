"""Training-backend tests — factory matrix, HTTP transport (urllib mocked),
and the scheduler's noop / http submission paths. No real network is ever
contacted; mirrors tests/test_zammad_connector.py.
"""

from __future__ import annotations

import io
import json
import urllib.error

import pytest

from fde_scope.flywheel import RetrainScheduler
from fde_scope.flywheel.backends import (
    ENV_TRAINING_TOKEN,
    ENV_TRAINING_URL,
    HTTPTrainingBackend,
    NoopBackend,
    TrainingBackendError,
    get_training_backend,
)

_URL = "https://training.example.com"
_TOKEN = "training-secret-token"


class _FakeResp:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *args) -> bool:
        return False

    def read(self) -> bytes:
        return self._body


@pytest.fixture()
def clean_training_env(monkeypatch):
    monkeypatch.delenv(ENV_TRAINING_URL, raising=False)
    monkeypatch.delenv(ENV_TRAINING_TOKEN, raising=False)
    return monkeypatch


# ---------------------------------------------------------------------------
# Factory matrix
# ---------------------------------------------------------------------------
def test_factory_noop_when_unconfigured(clean_training_env) -> None:
    backend = get_training_backend()
    assert isinstance(backend, NoopBackend)
    assert backend.name == "noop"


def test_factory_http_when_env_complete(clean_training_env) -> None:
    clean_training_env.setenv(ENV_TRAINING_URL, _URL)
    clean_training_env.setenv(ENV_TRAINING_TOKEN, _TOKEN)
    backend = get_training_backend()
    assert isinstance(backend, HTTPTrainingBackend)
    assert backend.name == "http"
    assert backend.base_url == _URL


@pytest.mark.parametrize("which", [ENV_TRAINING_URL, ENV_TRAINING_TOKEN])
def test_factory_partial_env_warns_and_noops(clean_training_env, caplog, which) -> None:
    clean_training_env.setenv(which, "value")
    with caplog.at_level("WARNING", logger="fde_scope.flywheel.backends"):
        backend = get_training_backend()
    assert isinstance(backend, NoopBackend)
    assert any("incomplete training backend configuration" in r.message for r in caplog.records)
    assert _TOKEN not in caplog.text


# ---------------------------------------------------------------------------
# HTTP backend — request shape
# ---------------------------------------------------------------------------
def test_http_submit_posts_job_spec_with_bearer(clean_training_env, monkeypatch) -> None:
    captured: dict = {}

    def fake_urlopen(request, timeout):  # noqa: ARG001
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["headers"] = {k.lower(): v for k, v in request.header_items()}
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeResp(b'{"job_id": "tj-42"}')

    monkeypatch.setattr("fde_scope.flywheel.backends.urllib.request.urlopen", fake_urlopen)
    backend = HTTPTrainingBackend(_URL, _TOKEN)
    job_spec = {"job": "weekly_incremental_retrain", "kind": "incremental", "sample_count": 250}
    job_id = backend.submit(job_spec)

    assert job_id == "tj-42"
    assert captured["url"] == f"{_URL}/jobs"
    assert captured["method"] == "POST"
    assert captured["headers"]["authorization"] == f"Bearer {_TOKEN}"
    assert captured["body"] == job_spec


def test_http_submit_accepts_bare_id_field(clean_training_env, monkeypatch) -> None:
    monkeypatch.setattr(
        "fde_scope.flywheel.backends.urllib.request.urlopen",
        lambda request, timeout: _FakeResp(b'{"id": 7}'),  # noqa: ARG005
    )
    assert HTTPTrainingBackend(_URL, _TOKEN).submit({"job": "x"}) == "7"


def test_http_status_gets_job_and_marks_backend(clean_training_env, monkeypatch) -> None:
    captured: dict = {}

    def fake_urlopen(request, timeout):  # noqa: ARG001
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        return _FakeResp(b'{"status": "running", "progress": 0.4}')

    monkeypatch.setattr("fde_scope.flywheel.backends.urllib.request.urlopen", fake_urlopen)
    status = HTTPTrainingBackend(_URL, _TOKEN).status("tj 42")

    assert captured["url"] == f"{_URL}/jobs/tj%2042"  # job id is URL-quoted
    assert captured["method"] == "GET"
    assert status["status"] == "running"
    assert status["backend"] == "http"
    assert status["job_id"] == "tj 42"


def test_http_cancel_posts_to_cancel_endpoint(clean_training_env, monkeypatch) -> None:
    captured: dict = {}

    def fake_urlopen(request, timeout):  # noqa: ARG001
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        return _FakeResp(b'{"status": "cancelled"}')

    monkeypatch.setattr("fde_scope.flywheel.backends.urllib.request.urlopen", fake_urlopen)
    result = HTTPTrainingBackend(_URL, _TOKEN).cancel("tj-42")

    assert captured["url"] == f"{_URL}/jobs/tj-42/cancel"
    assert captured["method"] == "POST"
    assert result["status"] == "cancelled"
    assert result["backend"] == "http"


# ---------------------------------------------------------------------------
# HTTP backend — error paths (token must never leak)
# ---------------------------------------------------------------------------
def test_http_401_raises_without_token(clean_training_env, monkeypatch) -> None:
    def fail(request, timeout):  # noqa: ARG001
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, io.BytesIO(b"bad"))

    monkeypatch.setattr("fde_scope.flywheel.backends.urllib.request.urlopen", fail)
    with pytest.raises(TrainingBackendError, match="401") as excinfo:
        HTTPTrainingBackend(_URL, _TOKEN).submit({"job": "x"})
    assert _TOKEN not in str(excinfo.value)


def test_http_timeout_raises_without_token(clean_training_env, monkeypatch) -> None:
    def fail(request, timeout):  # noqa: ARG001
        raise TimeoutError("read timed out")

    monkeypatch.setattr("fde_scope.flywheel.backends.urllib.request.urlopen", fail)
    with pytest.raises(TrainingBackendError, match="TimeoutError") as excinfo:
        HTTPTrainingBackend(_URL, _TOKEN).status("tj-42")
    assert _TOKEN not in str(excinfo.value)


def test_http_url_error_raises_without_token(clean_training_env, monkeypatch) -> None:
    def fail(request, timeout):  # noqa: ARG001
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("fde_scope.flywheel.backends.urllib.request.urlopen", fail)
    with pytest.raises(TrainingBackendError, match="URLError") as excinfo:
        HTTPTrainingBackend(_URL, _TOKEN).cancel("tj-42")
    assert _TOKEN not in str(excinfo.value)


def test_http_unexpected_response_shape_raises(clean_training_env, monkeypatch) -> None:
    monkeypatch.setattr(
        "fde_scope.flywheel.backends.urllib.request.urlopen",
        lambda request, timeout: _FakeResp(b'{"error": "oops"}'),  # noqa: ARG005
    )
    with pytest.raises(TrainingBackendError, match="unexpected training API response"):
        HTTPTrainingBackend(_URL, _TOKEN).submit({"job": "x"})


def test_http_backend_requires_url_and_token(clean_training_env) -> None:
    with pytest.raises(ValueError):
        HTTPTrainingBackend("", _TOKEN)
    with pytest.raises(ValueError):
        HTTPTrainingBackend(_URL, "")


# ---------------------------------------------------------------------------
# NoopBackend
# ---------------------------------------------------------------------------
def test_noop_backend_is_honest() -> None:
    backend = NoopBackend()
    job_id = backend.submit({"job": "x"})
    status = backend.status(job_id)
    assert status["backend"] == "noop"
    assert status["status"] == "submitted-stub"
    assert "not actually submitted" in status["detail"]
    cancel = backend.cancel(job_id)
    assert cancel["backend"] == "noop"
    assert cancel["status"] == "cancelled"


# ---------------------------------------------------------------------------
# Scheduler integration — noop and http paths
# ---------------------------------------------------------------------------
def test_scheduler_submit_via_noop(clean_training_env) -> None:
    sched = RetrainScheduler()
    job = sched.jobs[0]
    result = sched.submit(job, [{"id": "s1"}, {"id": "s2"}], engagement_id="eng-1")
    assert result["job"] == job.name
    assert result["kind"] == job.kind
    assert result["sample_count"] == 2
    assert result["status"] == "submitted"
    assert result["backend"] == "noop"
    assert "stub" not in result["status"]
    assert result["job_id"] == "noop-unsubmitted"
    # status is honestly labelled even through the scheduler
    assert sched.status(result["job_id"])["backend"] == "noop"


def test_scheduler_submit_via_http(clean_training_env, monkeypatch) -> None:
    clean_training_env.setenv(ENV_TRAINING_URL, _URL)
    clean_training_env.setenv(ENV_TRAINING_TOKEN, _TOKEN)
    captured: dict = {}

    def fake_urlopen(request, timeout):  # noqa: ARG001
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeResp(b'{"job_id": "tj-99"}')

    monkeypatch.setattr("fde_scope.flywheel.backends.urllib.request.urlopen", fake_urlopen)
    sched = RetrainScheduler()
    job = sched.jobs[0]
    result = sched.submit(
        job,
        [{"id": "s1"}, {"id": "s2"}],
        engagement_id="eng-1",
        data_window={"since": "2026-09-01", "until": "2026-09-28"},
        trigger_reason="weekly cron",
    )

    assert result["job_id"] == "tj-99"
    assert result["backend"] == "http"
    spec = captured["body"]
    assert spec["job"] == job.name
    assert spec["kind"] == "incremental"
    assert spec["sample_count"] == 2
    assert spec["sample_ids"] == ["s1", "s2"]
    assert spec["trigger"] == {
        "engagement_id": "eng-1",
        "data_window": {"since": "2026-09-01", "until": "2026-09-28"},
        "reason": "weekly cron",
    }
    # token never appears in the job spec or the scheduler result
    assert _TOKEN not in json.dumps(spec)
    assert _TOKEN not in json.dumps(result)


def test_scheduler_injected_backend_wins(clean_training_env) -> None:
    class _Spy:
        name = "spy"

        def __init__(self) -> None:
            self.specs: list[dict] = []

        def submit(self, job_spec: dict) -> str:
            self.specs.append(job_spec)
            return "spy-1"

        def status(self, job_id: str) -> dict:
            return {"job_id": job_id, "backend": self.name}

        def cancel(self, job_id: str) -> dict:
            return {"job_id": job_id, "backend": self.name}

    spy = _Spy()
    sched = RetrainScheduler(backend=spy)
    result = sched.submit(sched.jobs[1], [])
    assert result["backend"] == "spy"
    assert spy.specs[0]["job"] == "monthly_full_eval"
    assert spy.specs[0]["sample_count"] == 0
    assert spy.specs[0]["sample_ids"] == []
