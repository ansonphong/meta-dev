# Dispatch Table

Maps inbox item source tags to target agents, model tiers, and clearing
strategies. Used by inbox-clearer for routing cleared items.

## Default Dispatch

| Source Tag | Kind | Model | Strategy | Handler |
|------------|------|-------|----------|---------|
| `overlord_finding` | issue | sonnet | auto-resolve | fix-agent using `recommended_action` |
| `review_failure` | issue | sonnet | auto-resolve | `code-review-protocol` skill → sonnet fix-agent |
| `repair_dossier` | advisory | — | manual | surface to user (3 attempts already exhausted) |
| `sweep_anomaly` | issue | haiku | auto-resolve | haiku sweep-agent |
| `classify_blocked` | issue | sonnet | auto-resolve | re-run `/meta-classify` |
| `security_alert` | advisory | — | manual | NEVER auto-fix, surface advisory with options |
| `critical_structural` | advisory | opus | manual | spawn `Agent({ model: "opus", ... })` deep analysis |

## Routing Logic

1. Match item `source` tag against dispatch table
2. If matched: route to handler with specified model tier and strategy
3. If no match: remain open, surface to user for manual classification
4. If dispatch override exists in `plans/_dashboard/inbox.json`:

    ```json
    {
      "dispatch_overrides": {
        "overlord_finding": {
          "strategy": "manual",
          "reason": "Human review required for this project"
        }
      }
    }
    ```

    Apply override. Override takes precedence over default table.
