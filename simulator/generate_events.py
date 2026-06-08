import logging
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import psycopg2
from psycopg2 import OperationalError
from psycopg2.extras import execute_values


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


@dataclass(frozen=True)
class EventProfile:
    service_name: str
    endpoint: str
    event_type: str
    weight: int
    base_latency_ms: int
    value_range: Optional[tuple[float, float]] = None


DB_CONFIG = {
    "host": os.getenv("DB_HOST", "postgres"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "observability"),
    "user": os.getenv("DB_USER", "grafana"),
    "password": os.getenv("DB_PASSWORD", "grafana"),
    "connect_timeout": 5,
}

BATCH_SIZE = max(1, int(os.getenv("EVENT_BATCH_SIZE", "25")))
INTERVAL_SECONDS = max(1, int(os.getenv("EVENT_INTERVAL_SECONDS", "2")))

EVENT_PROFILES = [
    EventProfile("marketplace-web", "/", "page_view", 28, 75),
    EventProfile("marketplace-search", "/search", "search", 24, 135),
    EventProfile("marketplace-listing", "/listings/view", "listing_view", 20, 115),
    EventProfile("marketplace-contact", "/contact/click", "contact_click", 12, 155),
    EventProfile(
        "marketplace-listing",
        "/listings/create",
        "listing_created",
        9,
        210,
        (80.0, 650.0),
    ),
    EventProfile(
        "marketplace-payment",
        "/payment/checkout",
        "payment_attempt",
        7,
        285,
        (20.0, 420.0),
    ),
]

CITIES = [
    "Sao Paulo",
    "Rio de Janeiro",
    "Belo Horizonte",
    "Curitiba",
    "Recife",
    "Porto Alegre",
]

DEVICES = ["mobile", "desktop", "tablet"]


def connect_with_retry():
    while True:
        try:
            connection = psycopg2.connect(**DB_CONFIG)
            connection.autocommit = False
            logging.info(
                "Connected to PostgreSQL at %s:%s", DB_CONFIG["host"], DB_CONFIG["port"]
            )
            return connection
        except OperationalError as exc:
            logging.warning("PostgreSQL not ready yet: %s", exc)
            time.sleep(3)


def choose_profile() -> EventProfile:
    weights = [profile.weight for profile in EVENT_PROFILES]
    return random.choices(EVENT_PROFILES, weights=weights, k=1)[0]


def pick_status_code(profile: EventProfile) -> int:
    if profile.endpoint == "/payment/checkout":
        return random.choices(
            [200, 201, 400, 402, 500, 502, 503],
            weights=[55, 15, 8, 7, 7, 4, 4],
            k=1,
        )[0]

    return random.choices(
        [200, 201, 204, 400, 404, 429, 500],
        weights=[66, 14, 10, 4, 3, 2, 1],
        k=1,
    )[0]


def pick_latency(profile: EventProfile, status_code: int) -> int:
    latency = profile.base_latency_ms + random.randint(-35, 120)
    if status_code >= 500:
        latency += random.randint(180, 420)
    elif status_code >= 400:
        latency += random.randint(30, 120)
    return max(20, latency)


def pick_value(profile: EventProfile) -> Optional[float]:
    if profile.value_range is None:
        return None
    low, high = profile.value_range
    return round(random.uniform(low, high), 2)


def make_event(profile: EventProfile) -> tuple:
    status_code = pick_status_code(profile)
    event_time = datetime.now(timezone.utc) - timedelta(
        seconds=random.uniform(0, INTERVAL_SECONDS)
    )
    return (
        event_time,
        profile.service_name,
        profile.endpoint,
        status_code,
        pick_latency(profile, status_code),
        profile.event_type,
        random.randint(1000, 9999),
        pick_value(profile),
        random.choice(CITIES),
        random.choice(DEVICES),
    )


def insert_batch(connection, events: list[tuple]) -> None:
    with connection.cursor() as cursor:
        execute_values(
            cursor,
            """
            INSERT INTO observability.app_events (
                event_time,
                service_name,
                endpoint,
                status_code,
                latency_ms,
                event_type,
                user_id,
                value,
                city,
                device
            ) VALUES %s
            """,
            events,
        )
    connection.commit()


def main() -> None:
    connection = connect_with_retry()

    while True:
        try:
            events = [make_event(choose_profile()) for _ in range(BATCH_SIZE)]
            insert_batch(connection, events)
            logging.info("Inserted %s events", len(events))
            time.sleep(INTERVAL_SECONDS)
        except OperationalError as exc:
            logging.warning("Lost database connection: %s", exc)
            try:
                connection.close()
            except Exception:
                pass
            time.sleep(3)
            connection = connect_with_retry()
        except Exception:
            logging.exception("Unexpected failure while generating events")
            connection.rollback()
            time.sleep(2)


if __name__ == "__main__":
    main()
