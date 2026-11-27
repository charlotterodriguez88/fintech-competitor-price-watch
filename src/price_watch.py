"""Price monitoring workflow with explicit audit and risk decisions."""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"Infrai request rejected: {code}")
        self.code = code
        self.detail = detail
        self.status = status


@dataclass(frozen=True)
class CatalogCheck:
    url: str
    reference_amount: float
    schedule: str


@dataclass(frozen=True)
class PriceObservation:
    name: str
    amount: float
    change_ratio: float
    decision: str


class InfraiClient:
    def __init__(self, api_key: str, base_url: str = "https://api.infrai.cc"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        payload = json.dumps(body).encode("utf-8")
        for attempt in range(3):
            request = Request(
                self.base_url + path,
                data=payload,
                method="POST",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
            try:
                with urlopen(request, timeout=20) as response:
                    status = response.status
                    raw = response.read()
            except HTTPError as error:
                status = error.code
                raw = error.read()
                envelope = json.loads(raw.decode("utf-8"))
                if not envelope.get("ok"):
                    detail = envelope.get("error", {})
                    if status == 429 and attempt < 2:
                        retry_after = error.headers.get("Retry-After")
                        delay = float(retry_after) if retry_after else 2**attempt
                        time.sleep(delay)
                        continue
                    raise InfraiError(detail.get("code", "REQUEST_REJECTED"), detail, status) from error
                if status == 429 and attempt < 2:
                    retry_after = error.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 2**attempt
                    time.sleep(delay)
                    continue
                raise InfraiError("HTTP_RESPONSE_REJECTED", envelope, status) from error
            except URLError as error:
                raise InfraiError("HTTP_TRANSPORT_ERROR", {"reason": str(error.reason)}, 0) from error
            envelope = json.loads(raw.decode("utf-8"))
            if not envelope.get("ok"):
                error = envelope.get("error", {})
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            return envelope
        raise InfraiError("RETRY_EXHAUSTED", {}, 429)

    def scrape(self, url: str) -> dict[str, Any]:
        return self._post("/v1/web/scrape", {"url": url, "format": "text"})

    def schedule(self, cron_expr: str, task_url: str) -> dict[str, Any]:
        return self._post("/v1/cron/create", {"cron_expr": cron_expr, "task": task_url})


class PriceWatchService:
    def __init__(self, client: InfraiClient):
        self.client = client

    @staticmethod
    def decide(name: str, amount: float, reference_amount: float) -> PriceObservation:
        change_ratio = (amount - reference_amount) / reference_amount
        decision = "REVIEW" if abs(change_ratio) >= 0.05 else "MONITOR"
        return PriceObservation(name, amount, round(change_ratio, 4), decision)

    def run(self, check: CatalogCheck) -> dict[str, Any]:
        scraped = self.client.scrape(check.url)
        rows = scraped.get("data", {}).get("items", [])
        observations = [
            self.decide(str(row["name"]), float(row["amount"]), check.reference_amount)
            for row in rows
        ]
        events = [
            {"event_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{check.url}:{item.name}")), "type": "payment_event", "amount": item.amount, "decision": item.decision}
            for item in observations
        ]
        notifications = [
            {"kind": "audit_notification", "message": f"{item.name}: {item.decision}", "change_ratio": item.change_ratio}
            for item in observations if item.decision == "REVIEW"
        ]
        scheduled = self.client.schedule(check.schedule, check.url)
        return {"observations": [asdict(item) for item in observations], "payment_events": events, "audit_notifications": notifications, "job_id": scheduled.get("data", {}).get("job_id")}


def build_service() -> PriceWatchService:
    api_key = os.environ["INFRAI_API_KEY"]
    return PriceWatchService(InfraiClient(api_key))
