# Loop-Gap Integration

Single integration point. No coupling.

## On loop-gap completion

Loop-gap skill calls:
```bash
scripts/inbox-add.sh \
  --source loopgap_done \
  --kind advisory \
  --severity moderate \
  --title "loop-gap done on <plan> — ready for green-light?" \
  --body "Found X issues (Y auto-fixed), Z advisories." \
  --options '[{"label":"Approve → /meta-execute","command":"/meta-execute <plan>"},{"label":"Review again","command":"/loop-gap <plan>"}]' \
  --ref-file <plan-file>
```

Dashboard shows advisory with options. User picks one.
