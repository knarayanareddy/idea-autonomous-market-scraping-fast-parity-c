"""Apify and downstream cloud actor trigger dispatcher."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import requests

from .models import ParityDelta

logger = logging.getLogger("market_parity.apify_trigger")


class ApifyTriggerClient:
    """Dispatches deep scraping jobs to Apify actors only when local parity check fails."""

    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token or os.environ.get("APIFY_TOKEN", "").strip()

    def trigger_actor(
        self,
        actor_id: str,
        delta: ParityDelta,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Trigger an Apify actor with the delta payload."""
        if not delta.should_trigger_deep_scrape:
            logger.info("Skipping Apify trigger: Parity check confirmed zero actionable changes.")
            return {"status": "skipped", "reason": "in_parity"}

        payload = {
            "query": delta.query,
            "marketplace": delta.marketplace.value,
            "target_urls": [item.url for item in delta.new_listings]
            + [item[0].url for item in delta.price_drops],
            "new_count": len(delta.new_listings),
            "price_drop_count": len(delta.price_drops),
        }

        if dry_run or not self.api_token:
            mode = "[DRY-RUN]" if dry_run else "[NO-TOKEN (SIMULATED)]"
            logger.info(
                f"{mode} Dispatched Apify Actor '{actor_id}' for {len(payload['target_urls'])} URL(s)."
            )
            return {
                "status": "simulated",
                "actor_id": actor_id,
                "payload": payload,
                "note": "Apify token not provided or dry-run active; simulated cloud trigger.",
            }

        url = f"https://api.apify.com/v2/acts/{actor_id}/runs?token={self.api_token}"
        try:
            resp = requests.post(url, json=payload, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            run_id = data.get("data", {}).get("id")
            logger.info(f"Apify Actor triggered successfully (Run ID: {run_id})")
            return {"status": "triggered", "run_id": run_id, "data": data}
        except Exception as exc:
            logger.error(f"Failed to trigger Apify Actor: {exc}")
            return {"status": "error", "error": str(exc)}
