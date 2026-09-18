CREATE TABLE IF NOT EXISTS temporal_warrant_events (
    id TEXT PRIMARY KEY,
    warrant_id TEXT NOT NULL,
    from_status TEXT NOT NULL,
    to_status TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(warrant_id) REFERENCES temporal_warrants(id)
);

CREATE INDEX IF NOT EXISTS ix_temporal_warrant_events_warrant
ON temporal_warrant_events(warrant_id,created_at);

INSERT INTO temporal_warrant_events(id,warrant_id,from_status,to_status,reason,created_at)
SELECT lower(hex(randomblob(10))), id, '', status, 'migration snapshot', updated_at
FROM temporal_warrants
WHERE NOT EXISTS (
    SELECT 1 FROM temporal_warrant_events e WHERE e.warrant_id = temporal_warrants.id
);
