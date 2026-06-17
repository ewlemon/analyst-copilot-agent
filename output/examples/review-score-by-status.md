# Example: Average review score by order status

**Question asked:** *"What is the average review score by order status?"*

## The agent's answer

| Order status | Avg review score | Reviews |
|---|---|---|
| **Delivered** | 4.22 | 3,499 |
| **Processing** | 3.24 | 115 |
| **Shipped** | 3.22 | 220 |
| **Canceled** | 1.95 | 166 |

Delivered orders score highest (4.22/5) on by far the largest sample; canceled
orders score lowest (1.95), as expected. Processing and shipped sit in the
middle while customers await delivery.

*(The agent chose not to chart this one — a four-row table reads fine as text.)*

## The SQL the agent wrote

```sql
SELECT
  o.status,
  AVG(r.score) AS avg_review_score,
  COUNT(r.review_id) AS review_count
FROM orders o
LEFT JOIN reviews r ON o.order_id = r.order_id
GROUP BY o.status
ORDER BY avg_review_score DESC;
```

## Human-in-the-loop verification ✅

Re-ran independently; all four averages and counts matched (Delivered 4.22 /
3,499 … Canceled 1.95 / 166). The `LEFT JOIN` is the right choice so statuses
with no reviews wouldn't silently vanish.

**Caveat noted by the agent:** sample sizes differ sharply — the delivered
average rests on 3,499 reviews, the others on a few hundred or fewer, so the
non-delivered scores are noisier.
