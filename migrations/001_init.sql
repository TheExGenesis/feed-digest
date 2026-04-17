CREATE TABLE IF NOT EXISTS seen_items (
    item_id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    date_seen TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS digests (
    digest_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'composed',
    raw_item_count INTEGER DEFAULT 0,
    token_estimate INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS deliveries (
    digest_id TEXT PRIMARY KEY REFERENCES digests(digest_id),
    delivered_at TEXT,
    channel TEXT
);

CREATE TABLE IF NOT EXISTS publishes (
    digest_id TEXT PRIMARY KEY REFERENCES digests(digest_id),
    published_at TEXT,
    url TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
);
