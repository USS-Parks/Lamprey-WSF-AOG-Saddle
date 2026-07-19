"""Keep the WSF OpenAPI contract aligned with the hardened trust-plane routes."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def operation(document: dict, path: str, method: str) -> dict:
    return document["paths"][path][method]


class WsfOpenApiContract(unittest.TestCase):
    def test_privileged_routes_describe_their_authority_boundaries(self) -> None:
        # SAD-HIST-03 adapts the still-required intent from Mighty Eel source
        # commit 92dc928febb49837b71755ccb75a8eeccbe14b2b into current DTOs.
        document = json.loads(
            (REPO_ROOT / "crates" / "wsf-api" / "src" / "openapi.json").read_text(
                encoding="utf-8"
            )
        )

        issue = operation(document, "/v1/tokens/issue", "post")
        self.assertIn("authenticated principal", issue["summary"])
        self.assertIn("bounded intent", issue["summary"])
        self.assertLessEqual(
            {"200", "401", "403", "422", "502"}, issue["responses"].keys()
        )

        attenuate = operation(document, "/v1/tokens/attenuate", "post")
        self.assertIn("authenticated parent", attenuate["summary"])
        self.assertIn("current revocation", attenuate["summary"])
        self.assertIn("every authority axis", attenuate["summary"])
        self.assertLessEqual(
            {"200", "401", "403", "422"}, attenuate["responses"].keys()
        )

        exchange = operation(document, "/v1/credentials/exchange", "post")
        self.assertIn("tenant-scoped named grant", exchange["summary"])
        self.assertIn("never supply a raw role ARN", exchange["summary"])
        self.assertLessEqual(
            {"200", "401", "403", "422"}, exchange["responses"].keys()
        )

        receipts = operation(document, "/v1/receipts", "get")
        self.assertIn("tenant-scoped to the authenticated principal", receipts["summary"])
        self.assertIn("enrolled global auditor", receipts["summary"])
        self.assertEqual(
            [parameter["name"] for parameter in receipts["parameters"]],
            ["field", "value"],
        )
        self.assertLessEqual(
            {"200", "401", "403"}, receipts["responses"].keys()
        )

        export = operation(document, "/v1/receipts/export", "get")
        self.assertIn("global auditors only", export["summary"])


if __name__ == "__main__":
    unittest.main()
