// Neo4j Migration 002 — Create uniqueness constraints
//
// FUTURE DEVELOPMENT:
// - CREATE CONSTRAINT bc_id_unique IF NOT EXISTS FOR (bc:BoundedContext) REQUIRE bc.id IS UNIQUE
// - CREATE CONSTRAINT class_id_unique IF NOT EXISTS FOR (c:Class) REQUIRE c.id IS UNIQUE
// - CREATE CONSTRAINT drift_id_unique IF NOT EXISTS FOR (d:DriftAlert) REQUIRE d.id IS UNIQUE
// - Uniqueness constraints prevent duplicate nodes during re-runs and concurrent jobs.
