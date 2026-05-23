# MAI Alerting Rules (SHIP-11)

`mai-alerts.yml` is a Prometheus alerting rule file that covers the
13 alerts mandated by `docs/SHIP-HARDENING-PLAN.md` §10.

## Install

Copy `mai-alerts.yml` into the Prometheus server's rule directory and
reference it from `prometheus.yml`:

```yaml
rule_files:
  - "/etc/prometheus/rules/mai-alerts.yml"
```

Then reload Prometheus:

```sh
systemctl reload prometheus
# or, if running by hand:
curl -X POST http://localhost:9090/-/reload
```

Validate the rule file before deploying:

```sh
promtool check rules /etc/prometheus/rules/mai-alerts.yml
```

## Severity matrix

| label    | meaning                                                  | typical routing                       |
|----------|----------------------------------------------------------|---------------------------------------|
| `page`   | wake an oncall human at any hour                         | PagerDuty / Opsgenie page             |
| `ticket` | business-hours triage; SLO-relevant but not pageable     | Jira / Linear / GitHub issue          |
| `info`   | informational; surfaced on dashboards, not paged         | Grafana annotation                    |

## Notes for operators

* `BackupFailed` references metrics produced by SHIP-09 / SHIP-10.
  Until those ship, the underlying counter (`mai_backup_failure_total`)
  is always zero and the rule cannot fire. The rule is intentionally
  wired today so the alerting harness is in place before the producer
  side lands.
* `DiskNearFull` depends on the `node_exporter` filesystem metrics —
  install `node_exporter` on every MAI host and ensure it exports
  `node_filesystem_avail_bytes` for `/var/lib/mai*` and `/var/log/mai*`.
* The `for:` durations are intentionally conservative. Production
  profiles can override them with a thinner copy of this file later in
  the rule_files load order.
