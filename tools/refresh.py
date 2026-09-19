#!/usr/bin/env python3
"""Pull the Musical Chairs project out of Linear and write progress.json.

Usage: LINEAR_API_KEY=... python tools/refresh.py site/data/progress.json

Stdlib only so the GitHub Action needs no pip step.
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

PROJECT_ID = "97d7a2bd-d50a-452e-a2ec-e65b7a915900"
PROJECT_NAME = "Barknito Musical Chairs"
ENDPOINT = "https://api.linear.app/graphql"

QUERY = """
query Issues($projectId: ID, $after: String) {
  issues(first: 100, after: $after, filter: { project: { id: { eq: $projectId } } }) {
    pageInfo { hasNextPage endCursor }
    nodes {
      identifier title description url dueDate startedAt completedAt canceledAt
      state { name type }
      projectMilestone { name }
      relations { nodes { type relatedIssue { identifier } } }
    }
  }
}
"""

ESTIMATE_RE = re.compile(r"Estimate:\s*([0-9]+(?:\.[0-9]+)?)\s*days?", re.IGNORECASE)
MC_RE = re.compile(r"^(MC-\d{3})\s+(.*)$")


def graphql(key, query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers={"Content-Type": "application/json", "Authorization": key},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        raise SystemExit(f"Linear returned errors: {payload['errors']}")
    return payload["data"]


def fetch_issues(key):
    nodes = []
    after = None
    while True:
        data = graphql(key, QUERY, {"projectId": PROJECT_ID, "after": after})
        page = data["issues"]
        nodes.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            return nodes
        after = page["pageInfo"]["endCursor"]


def build(nodes):
    by_issue = {}
    tasks = []
    for n in nodes:
        m = MC_RE.match(n["title"])
        if not m:
            continue
        mc, title = m.group(1), m.group(2)
        est = ESTIMATE_RE.search(n.get("description") or "")
        milestone_name = (n.get("projectMilestone") or {}).get("name") or ""
        task = {
            "id": mc,
            "issue": n["identifier"],
            "title": title,
            "url": n["url"],
            "milestone": milestone_name.split(" ")[0] if milestone_name else None,
            "milestoneName": milestone_name or None,
            "status": n["state"]["type"],
            "statusName": n["state"]["name"],
            "effort": float(est.group(1)) if est else None,
            "due": n.get("dueDate"),
            "startedAt": n.get("startedAt"),
            "completedAt": n.get("completedAt"),
            "canceledAt": n.get("canceledAt"),
            "blocks": [],
            "blockedBy": [],
        }
        by_issue[n["identifier"]] = task
        tasks.append(task)
    for n in nodes:
        src = by_issue.get(n["identifier"])
        if not src:
            continue
        for rel in n["relations"]["nodes"]:
            if rel["type"] != "blocks":
                continue
            dst = by_issue.get(rel["relatedIssue"]["identifier"])
            if not dst:
                continue
            src["blocks"].append(dst["id"])
            dst["blockedBy"].append(src["id"])
    for t in tasks:
        t["blocks"].sort()
        t["blockedBy"].sort()
    tasks.sort(key=lambda t: t["id"])
    return tasks


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "site/data/progress.json"
    key = os.environ.get("LINEAR_API_KEY")
    if not key:
        raise SystemExit("LINEAR_API_KEY is not set")
    nodes = fetch_issues(key)
    tasks = build(nodes)
    doc = {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project": PROJECT_NAME,
        "tasks": tasks,
    }
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as f:
        json.dump(doc, f, indent=1)
    missing = [t["id"] for t in tasks if t["effort"] is None]
    print(f"wrote {out}: {len(tasks)} tasks, {len(missing)} without an estimate {missing}")


if __name__ == "__main__":
    main()
