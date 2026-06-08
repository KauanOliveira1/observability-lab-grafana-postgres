CREATE SCHEMA IF NOT EXISTS observability;

CREATE TABLE IF NOT EXISTS observability.app_events (
    id BIGSERIAL PRIMARY KEY,
    event_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    service_name TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    status_code INT NOT NULL,
    latency_ms INT NOT NULL,
    event_type TEXT NOT NULL,
    user_id INT NOT NULL,
    value NUMERIC(10,2),
    city TEXT,
    device TEXT
);

CREATE INDEX IF NOT EXISTS idx_app_events_event_time
    ON observability.app_events (event_time);

CREATE INDEX IF NOT EXISTS idx_app_events_endpoint_event_time
    ON observability.app_events (endpoint, event_time);

CREATE INDEX IF NOT EXISTS idx_app_events_event_type_event_time
    ON observability.app_events (event_type, event_time);
