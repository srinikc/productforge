-- BI-PF-1271 / Epic BI-PF-1265: Revert alert policy tables.

DROP TABLE IF EXISTS alert_throttle_state;
DROP TABLE IF EXISTS alert_rules;
