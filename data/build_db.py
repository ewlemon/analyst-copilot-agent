"""Build the local analytics database the agent queries.

By default this generates a *seeded synthetic* e-commerce dataset so the whole
project runs with zero external downloads. The data is random but deterministic
(same seed → same database every time), with realistic structure: related
tables, regional skew, category margins, seasonality, and review scores that
correlate with order status.

Run it with:

    python data/build_db.py

It writes ``data/analytics.db``. To use the real Olist Brazilian E-Commerce
dataset instead, see ``data/README.md``.

Only the Python standard library is used here, so this script works even before
you have installed the project requirements.
"""

from __future__ import annotations

import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_PATH = Path(__file__).resolve().parent / "analytics.db"
SEED = 42

N_CUSTOMERS = 1_500
N_ORDERS = 4_000
START_DATE = date(2023, 1, 1)
END_DATE = date(2024, 12, 31)

# Brazilian states with rough relative weights (keeps the "Olist" flavor so the
# schema maps cleanly onto the real dataset later).
STATES = {
    "SP": 42, "RJ": 13, "MG": 12, "RS": 6, "PR": 6, "SC": 4,
    "BA": 4, "DF": 3, "GO": 3, "ES": 2, "PE": 2, "CE": 2, "PA": 1,
}
CITY_BY_STATE = {
    "SP": "Sao Paulo", "RJ": "Rio de Janeiro", "MG": "Belo Horizonte",
    "RS": "Porto Alegre", "PR": "Curitiba", "SC": "Florianopolis",
    "BA": "Salvador", "DF": "Brasilia", "GO": "Goiania", "ES": "Vitoria",
    "PE": "Recife", "CE": "Fortaleza", "PA": "Belem",
}

# category -> (min_price, max_price, gross_margin). Margin drives "which
# categories are most profitable" style questions.
CATEGORIES = {
    "electronics":      (120.0, 900.0, 0.18),
    "home_appliances":  (80.0, 600.0, 0.22),
    "furniture":        (150.0, 1200.0, 0.30),
    "toys":             (20.0, 150.0, 0.40),
    "health_beauty":    (15.0, 120.0, 0.45),
    "sports_leisure":   (30.0, 400.0, 0.35),
    "books":            (10.0, 80.0, 0.25),
    "garden_tools":     (25.0, 300.0, 0.28),
}

ORDER_STATUSES = {"delivered": 88, "shipped": 5, "canceled": 4, "processing": 3}
PAYMENT_TYPES = {"credit_card": 74, "boleto": 18, "voucher": 5, "debit_card": 3}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def weighted_choice(rng: random.Random, weights: dict[str, int]) -> str:
    """Pick a key from {value: weight} proportional to its weight."""
    keys = list(weights.keys())
    return rng.choices(keys, weights=list(weights.values()), k=1)[0]


def random_date(rng: random.Random) -> date:
    """A date in [START_DATE, END_DATE] with a mild Nov/Dec sales bump."""
    span = (END_DATE - START_DATE).days
    day = START_DATE + timedelta(days=rng.randint(0, span))
    # Re-roll some dates into Nov/Dec to create holiday seasonality.
    if day.month not in (11, 12) and rng.random() < 0.18:
        year = rng.choice([2023, 2024])
        month = rng.choice([11, 12])
        day = date(year, month, rng.randint(1, 28))
    return day


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA = """
DROP TABLE IF EXISTS reviews;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id    TEXT PRIMARY KEY,
    customer_state TEXT NOT NULL,
    customer_city  TEXT NOT NULL,
    signup_date    TEXT NOT NULL
);

CREATE TABLE products (
    product_id TEXT PRIMARY KEY,
    category   TEXT NOT NULL,
    base_price REAL NOT NULL,
    unit_cost  REAL NOT NULL
);

CREATE TABLE orders (
    order_id    TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    order_date  TEXT NOT NULL,
    status      TEXT NOT NULL
);

CREATE TABLE order_items (
    order_item_id INTEGER PRIMARY KEY,
    order_id      TEXT NOT NULL REFERENCES orders(order_id),
    product_id    TEXT NOT NULL REFERENCES products(product_id),
    quantity      INTEGER NOT NULL,
    price         REAL NOT NULL
);

CREATE TABLE payments (
    payment_id   INTEGER PRIMARY KEY,
    order_id     TEXT NOT NULL REFERENCES orders(order_id),
    payment_type TEXT NOT NULL,
    installments INTEGER NOT NULL,
    value        REAL NOT NULL
);

CREATE TABLE reviews (
    review_id   TEXT PRIMARY KEY,
    order_id    TEXT NOT NULL REFERENCES orders(order_id),
    score       INTEGER NOT NULL,
    review_date TEXT NOT NULL
);
"""


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def build() -> None:
    rng = random.Random(SEED)
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)

    # --- customers ---
    customers = []
    for i in range(N_CUSTOMERS):
        state = weighted_choice(rng, STATES)
        customers.append((
            f"cust_{i:05d}",
            state,
            CITY_BY_STATE[state],
            random_date(rng).isoformat(),
        ))
    conn.executemany("INSERT INTO customers VALUES (?,?,?,?)", customers)

    # --- products ---
    products = []
    n_products = 200
    for i in range(n_products):
        category = rng.choice(list(CATEGORIES))
        lo, hi, _margin = CATEGORIES[category]
        base_price = round(rng.uniform(lo, hi), 2)
        margin = CATEGORIES[category][2]
        unit_cost = round(base_price * (1 - margin), 2)
        products.append((f"prod_{i:04d}", category, base_price, unit_cost))
    conn.executemany("INSERT INTO products VALUES (?,?,?,?)", products)

    customer_ids = [c[0] for c in customers]
    product_ids = [p[0] for p in products]
    product_price = {p[0]: p[2] for p in products}

    # --- orders, order_items, payments, reviews ---
    orders, items, payments, reviews = [], [], [], []
    item_id = 0
    payment_id = 0
    for o in range(N_ORDERS):
        order_id = f"order_{o:06d}"
        customer_id = rng.choice(customer_ids)
        order_date = random_date(rng)
        status = weighted_choice(rng, ORDER_STATUSES)
        orders.append((order_id, customer_id, order_date.isoformat(), status))

        # 1-4 line items, each a random product with a price near its base.
        order_total = 0.0
        for _ in range(rng.randint(1, 4)):
            product_id = rng.choice(product_ids)
            quantity = rng.randint(1, 3)
            # Sale price wiggles +/- 8% around the product's base price.
            price = round(product_price[product_id] * rng.uniform(0.92, 1.08), 2)
            items.append((item_id, order_id, product_id, quantity, price))
            order_total += price * quantity
            item_id += 1

        # One payment covering the order total (+ small shipping), split into
        # installments for credit cards.
        ptype = weighted_choice(rng, PAYMENT_TYPES)
        installments = rng.randint(1, 10) if ptype == "credit_card" else 1
        value = round(order_total + rng.uniform(5, 35), 2)
        payments.append((payment_id, order_id, ptype, installments, value))
        payment_id += 1

        # Reviews: delivered orders skew to 4-5 stars; problem orders skew low.
        if status == "delivered":
            score = rng.choices([5, 4, 3, 2, 1], weights=[55, 25, 10, 6, 4])[0]
        elif status in ("shipped", "processing"):
            score = rng.choices([5, 4, 3, 2, 1], weights=[20, 25, 25, 18, 12])[0]
        else:  # canceled
            score = rng.choices([5, 4, 3, 2, 1], weights=[5, 8, 15, 27, 45])[0]
        review_date = order_date + timedelta(days=rng.randint(2, 20))
        reviews.append((f"rev_{o:06d}", order_id, score, review_date.isoformat()))

    conn.executemany("INSERT INTO orders VALUES (?,?,?,?)", orders)
    conn.executemany("INSERT INTO order_items VALUES (?,?,?,?,?)", items)
    conn.executemany("INSERT INTO payments VALUES (?,?,?,?,?)", payments)
    conn.executemany("INSERT INTO reviews VALUES (?,?,?,?)", reviews)

    # Helpful indexes for the kinds of joins the agent will write.
    conn.executescript(
        """
        CREATE INDEX idx_orders_customer ON orders(customer_id);
        CREATE INDEX idx_items_order ON order_items(order_id);
        CREATE INDEX idx_items_product ON order_items(product_id);
        CREATE INDEX idx_payments_order ON payments(order_id);
        CREATE INDEX idx_reviews_order ON reviews(order_id);
        """
    )
    conn.commit()

    counts = {
        t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("customers", "products", "orders", "order_items", "payments", "reviews")
    }
    conn.close()

    print(f"Built {DB_PATH}")
    for table, n in counts.items():
        print(f"  {table:<12} {n:>6,} rows")


if __name__ == "__main__":
    build()
