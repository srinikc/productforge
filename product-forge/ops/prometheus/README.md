# Backlog authority Prometheus wiring

`backlog-authority.rules.yml` is the alert rule fragment.

`prometheus.yml` is an **example** scrape configuration, not a replacement for an existing
Prometheus deployment. In a shared deployment:

1. Copy `backlog-authority.rules.yml` into the deployment's rule directory.
2. Add it to the existing `rule_files:` list.
3. Add an `edpsvc` scrape target if one is not already present.
4. Put the EDP admin token in the deployment's secret file referenced by
   `authorization.credentials_file`; rotate it with the service token.

The `/metrics` endpoint is admin-protected. Do not expose it publicly.
