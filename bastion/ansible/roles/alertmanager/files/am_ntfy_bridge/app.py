import os

import requests
from fastapi import FastAPI, HTTPException, Request

app = FastAPI()

NTFY_BASE_URL = os.environ["NTFY_BASE_URL"].rstrip("/")
NTFY_TOPIC = os.environ["NTFY_TOPIC"]
NTFY_USER = os.getenv("NTFY_USER")
NTFY_PASS = os.getenv("NTFY_PASS")
NTFY_TOKEN = os.getenv("NTFY_TOKEN")

SEV_PRIORITY = {
    "critical": "5",
    "warning": "3",
    "info": "2",
}


def _auth_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    if NTFY_TOKEN:
        headers["Authorization"] = f"Bearer {NTFY_TOKEN}"
    return headers


def _auth() -> tuple[str, str] | None:
    if NTFY_USER and NTFY_PASS:
        return (NTFY_USER, NTFY_PASS)
    return None


@app.post("/alertmanager")
async def alertmanager_webhook(req: Request) -> dict[str, bool]:
    payload = await req.json()

    alerts = payload.get("alerts", [])
    common_labels = payload.get("commonLabels", {}) or {}
    common_ann = payload.get("commonAnnotations", {}) or {}
    status = payload.get("status", "firing")

    alertname = common_labels.get("alertname", "Alert")
    severity = common_labels.get("severity", "info")
    priority = SEV_PRIORITY.get(severity, "2")

    summary = common_ann.get("summary") or common_ann.get("title") or ""
    description = common_ann.get("description") or ""

    lines: list[str] = []
    if summary:
        lines.append(summary)
    if description:
        lines.append(description)

    for alert in alerts[:10]:
        labels = alert.get("labels", {}) or {}
        annotations = alert.get("annotations", {}) or {}
        instance = labels.get("instance", "")
        job = labels.get("job", "")
        short_summary = annotations.get("summary", "")
        line = (
            f"- {labels.get('alertname', '')} {severity} "
            f"{job} {instance} {short_summary}"
        ).strip()
        lines.append(line)

    if len(alerts) > 10:
        lines.append(f"... and {len(alerts) - 10} more")

    title = f"[{status.upper()}] {alertname}"
    tags = ",".join(
        filter(
            None,
            [severity, common_labels.get("job", ""), common_labels.get("instance", "")],
        )
    )

    url = f"{NTFY_BASE_URL}/{NTFY_TOPIC}"
    headers = {
        "Title": title,
        "Priority": priority,
        "Tags": tags,
        **_auth_headers(),
    }

    body = "\n".join(lines) if lines else title

    response = requests.post(
        url,
        data=body.encode("utf-8"),
        headers=headers,
        auth=_auth(),
        timeout=5,
    )
    if response.status_code >= 300:
        raise HTTPException(
            status_code=502,
            detail=(
                "ntfy publish failed: "
                f"{response.status_code} {response.text[:200]}"
            ),
        )

    return {"ok": True}
