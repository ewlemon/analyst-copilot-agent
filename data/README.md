# Data

The agent queries a local SQLite database, `analytics.db`, that models an
e-commerce business with six related tables.

## Quick start (default - synthetic data)

```bash
python data/build_db.py
```

This generates a **seeded synthetic** dataset (deterministic - same data every
run) and writes `data/analytics.db`. No downloads, no accounts, no API key
needed. This is the path the tests and examples assume.

## Schema

| Table | Grain | Key columns |
|---|---|---|
| `customers` | one row per customer | `customer_id`, `customer_state`, `customer_city`, `signup_date` |
| `products` | one row per product | `product_id`, `category`, `base_price`, `unit_cost` |
| `orders` | one row per order | `order_id`, `customer_id`, `order_date`, `status` |
| `order_items` | one row per line item | `order_id`, `product_id`, `quantity`, `price` |
| `payments` | one row per payment | `order_id`, `payment_type`, `installments`, `value` |
| `reviews` | one row per review | `order_id`, `score` (1-5), `review_date` |

**Conventions**
- *Revenue* = `SUM(order_items.price * order_items.quantity)`.
- *Gross profit* ≈ `SUM((order_items.price - products.unit_cost) * order_items.quantity)`
  (join `order_items` → `products`).
- *Region* = `customers.customer_state` (join `orders` → `customers`).

## Optional: use the real Olist dataset

For extra credibility you can swap in the real **Olist Brazilian E-Commerce**
dataset (~100k orders) instead of the synthetic one. It is a well-known public
dataset on Kaggle.

1. Download it from
   <https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce> (free Kaggle
   account required) and unzip the CSVs into `data/raw/`.
2. The Olist tables map onto this project's schema as follows:
   - `olist_customers_dataset.csv` → `customers`
   - `olist_products_dataset.csv` → `products`
   - `olist_orders_dataset.csv` → `orders`
   - `olist_order_items_dataset.csv` → `order_items`
   - `olist_order_payments_dataset.csv` → `payments`
   - `olist_order_reviews_dataset.csv` → `reviews`
3. Write a loader that reads those CSVs and inserts them into the same schema
   (`build_db.py` is structured so this is a contained change). Keeping the
   column names identical means **none of the agent code changes** - only the
   data source does.

> The synthetic generator deliberately uses Brazilian state codes and similar
> category names so this swap is low-friction. Raw data and the `.db` file are
> gitignored and never committed.
