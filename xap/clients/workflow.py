"""
xap/clients/workflow.py — Causal chain and workflow queries.
"""
import httpx


class WorkflowClient:
    def __init__(self, base_url: str = "https://api.zexrail.com"):
        self.base_url = base_url

    async def get_chain(self, receipt_id: str) -> dict:
        """Get the full causal chain for a receipt, root first."""
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{self.base_url}/xap/v1/verity/receipts/{receipt_id}/chain"
            )
            r.raise_for_status()
            return r.json()

    async def get_workflow(self, workflow_id: str) -> dict:
        """Get all receipts in a workflow."""
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{self.base_url}/xap/v1/verity/workflows/{workflow_id}"
            )
            r.raise_for_status()
            return r.json()

    async def verify_workflow(self, workflow_id: str) -> dict:
        """Verify every receipt in a workflow and return aggregate result."""
        from xap.verify import verify_receipt_full
        workflow = await self.get_workflow(workflow_id)
        results = []
        for receipt in workflow["receipts"]:
            try:
                rv = await verify_receipt_full(receipt["id"], self.base_url)
                results.append({
                    "receipt_id": receipt["id"],
                    "depth": receipt.get("causal_depth"),
                    "outcome": rv.outcome,
                    "replay_verified": rv.replay_verified,
                    "tsa_anchored": rv.tsa_anchored,
                    "policy_verified": rv.policy_verified,
                })
            except Exception as e:
                results.append({"receipt_id": receipt["id"], "error": str(e)})

        all_valid = all(r.get("replay_verified") for r in results if "error" not in r)
        return {
            "workflow_id": workflow_id,
            "receipt_count": len(results),
            "all_valid": all_valid,
            "results": results,
        }
