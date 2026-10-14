-- 0002 down: drop the EDP-17 core schema (reverse dependency order).
DROP TABLE IF EXISTS quotas;
DROP TABLE IF EXISTS usage;
DROP TABLE IF EXISTS attempts;
DROP TABLE IF EXISTS stages;
DROP TABLE IF EXISTS runs;
DROP TABLE IF EXISTS projects;
DROP TABLE IF EXISTS memberships;
DROP TABLE IF EXISTS tenants;
