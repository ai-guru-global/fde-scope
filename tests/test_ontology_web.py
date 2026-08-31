"""ontology web 只读路由。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from fde_scope.web.app import app

client = TestClient(app)


def test_list_schemas_contains_builtin() -> None:
    resp = client.get("/api/ontology/schemas")
    assert resp.status_code == 200
    ids = {e["id"] for e in resp.json()}
    assert {"fde-core", "mfg-overlay"} <= ids


def test_schema_detail_and_404() -> None:
    resp = client.get("/api/ontology/schema/fde-core")
    assert resp.status_code == 200
    assert resp.json()["id"] == "fde-core"
    assert client.get("/api/ontology/schema/ghost").status_code == 404


def test_store_detail_and_404() -> None:
    assert client.get("/api/ontology/store/ghost").status_code == 404
