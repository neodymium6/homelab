import hashlib
import json
import os
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request

NTFY_BASE_URL = os.environ["NTFY_BASE_URL"].rstrip("/")
NTFY_TOPIC = os.environ["NTFY_TOPIC"]
NTFY_USER = os.getenv("NTFY_USER")
NTFY_PASS = os.getenv("NTFY_PASS")
NTFY_TOKEN = os.getenv("NTFY_TOKEN")

NTFY_ICON_URL = os.getenv("NTFY_ICON_URL")
USE_SEQUENCE_ID = os.getenv("NTFY_USE_SEQUENCE_ID", "1") != "0"
MAX_BODY_BYTES = int(os.getenv("NTFY_MAX_BODY_BYTES", "3500"))

SEV = {
    "critical": {"priority": "5", "tag": "critical"},
    "warning": {"priority": "4", "tag": "warning"},
    "info": {"priority": "3", "tag": "info"},
}
STATUS = {
    "firing": {"tag": "firing"},
    "resolved": {"tag": "resolved"},
}


def _auth_headers() -> dict[str, str]:
    if NTFY_TOKEN:
        return {"Authorization": f"Bearer {NTFY_TOKEN}"}
    return {}


def _auth() -> tuple[str, str] | None:
    if NTFY_USER and NTFY_PASS:
        return (NTFY_USER, NTFY_PASS)
    return None


def _truncate_utf8(value: str, max_bytes: int) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value

    chunk = encoded[: max_bytes - 3]
    while chunk:
        try:
            return chunk.decode("utf-8") + "..."
        except UnicodeDecodeError:
            chunk = chunk[:-1]
    return "..."


def _stable_sequence_id(payload: dict[str, Any]) -> str:
    key = payload.get("groupKey")
    if not key:
        key = json.dumps(
            payload.get("groupLabels", {}) or {},
            sort_keys=True,
            ensure_ascii=False,
        )
    digest = hashlib.sha1(str(key).encode("utf-8")).hexdigest()
    return digest[:12]


def _pick_severity(payload: dict[str, Any]) -> str:
    common_labels = payload.get("commonLabels", {}) or {}
    if common_labels.get("severity"):
        return str(common_labels["severity"])

    alerts = payload.get("alerts", []) or []
    if alerts and (alerts[0].get("labels") or {}).get("severity"):
        return str(alerts[0]["labels"]["severity"])

    return "info"

def _tag(value: str) -> str:
    return value.strip().replace(" ", "-")


def _build_markdown(payload: dict[str, Any], severity: str) -> tuple[str, str, str, str, str]:
    alerts = payload.get("alerts", []) or []
    common_labels = payload.get("commonLabels", {}) or {}
    common_ann = payload.get("commonAnnotations", {}) or {}
    status = str(payload.get("status", "firing"))

    sev_cfg = SEV.get(severity, SEV["info"])
    st_cfg = STATUS.get(status, STATUS["firing"])

    alertname = str(common_labels.get("alertname") or "Alert")
    job = str(common_labels.get("job") or "")
    instance = str(common_labels.get("instance") or "")

    summary = str(common_ann.get("summary") or common_ann.get("title") or "")
    description = str(common_ann.get("description") or "")
    runbook_url = str(common_ann.get("runbook_url") or "")

    title = f"[{status.upper()}][{severity.upper()}] {alertname}"

    tag_values = [_tag(st_cfg["tag"]), _tag(sev_cfg["tag"])]
    if job:
        tag_values.append(_tag(job))
    if instance:
        tag_values.append(_tag(instance))
    tags = ",".join(filter(None, tag_values))

    actions: list[str] = []
    if runbook_url:
        actions.append(f"view, Runbook, {runbook_url}")
    actions_header = "; ".join(actions[:3])

    lines: list[str] = []
    if summary:
        lines.append(f"**{summary}**")
    else:
        lines.append(f"**{alertname}**")

    if description:
        lines.extend(["", description])

    lines.extend(
        [
            "",
            f"- **Status**: `{status}`",
            f"- **Severity**: `{severity}`",
        ]
    )
    if job:
        lines.append(f"- **Job**: `{job}`")
    if instance:
        lines.append(f"- **Instance**: `{instance}`")
    lines.append(f"- **Alerts**: `{len(alerts)}`")

    if runbook_url:
        lines.append(f"[Runbook]({runbook_url})")

    if alerts:
        lines.extend(["", "### Details"])
        for alert in alerts[:10]:
            labels = alert.get("labels", {}) or {}
            ann = alert.get("annotations", {}) or {}
            item_name = str(labels.get("alertname") or "")
            item_job = str(labels.get("job") or job)
            item_instance = str(labels.get("instance") or instance)
            item_summary = str(ann.get("summary") or "")
            starts_at = str(alert.get("startsAt") or "")

            head = f"- `{item_name}`"
            tail_bits = [part for part in [item_job, item_instance] if part]
            if tail_bits:
                head += " (" + " / ".join(tail_bits) + ")"
            if item_summary:
                head += f": {item_summary}"
            lines.append(head)
            if starts_at:
                lines.append(f"  - startsAt: `{starts_at}`")

        if len(alerts) > 10:
            lines.append(f"- ... and {len(alerts) - 10} more")

    body = _truncate_utf8("\n".join(lines), MAX_BODY_BYTES)
    return title, tags, str(sev_cfg["priority"]), body, actions_header


@asynccontextmanager
async def lifespan(app: FastAPI):
    timeout = httpx.Timeout(5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        app.state.http = client
        yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}


@app.post("/alertmanager")
async def alertmanager_webhook(req: Request) -> dict[str, bool]:
    try:
        payload = await req.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid JSON payload") from exc

    severity = _pick_severity(payload)
    title, tags, priority, body, actions_header = _build_markdown(payload, severity)

    if USE_SEQUENCE_ID:
        sequence_id = _stable_sequence_id(payload)
        url = f"{NTFY_BASE_URL}/{NTFY_TOPIC}/{sequence_id}"
    else:
        url = f"{NTFY_BASE_URL}/{NTFY_TOPIC}"

    headers: dict[str, str] = {
        "Title": title,
        "Priority": priority,
        "Tags": tags,
        "Markdown": "yes",
        **_auth_headers(),
    }

    if actions_header:
        headers["Actions"] = actions_header
    if NTFY_ICON_URL:
        headers["Icon"] = NTFY_ICON_URL

    client: httpx.AsyncClient = req.app.state.http
    try:
        response = await client.post(
            url,
            content=body.encode("utf-8"),
            headers=headers,
            auth=_auth(),
        )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"ntfy publish failed: {exc}") from exc

    if response.status_code >= 300:
        raise HTTPException(
            status_code=502,
            detail=f"ntfy publish failed: {response.status_code} {response.text[:200]}",
        )

    return {"ok": True}
