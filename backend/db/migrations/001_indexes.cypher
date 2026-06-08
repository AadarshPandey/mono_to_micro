// Neo4j Migration 001 — Create indexes for performance
//
// FUTURE DEVELOPMENT:
// - CREATE INDEX class_name_idx IF NOT EXISTS FOR (c:Class) ON (c.name)
// - CREATE INDEX class_id_idx IF NOT EXISTS FOR (c:Class) ON (c.id)
// - CREATE INDEX method_fqn_idx IF NOT EXISTS FOR (m:Method) ON (m.id)
// - CREATE INDEX class_job_idx IF NOT EXISTS FOR (c:Class) ON (c.job_id)
// - These indexes accelerate graph_builder writes and Louvain clustering queries.
