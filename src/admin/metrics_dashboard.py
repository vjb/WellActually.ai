# Admin Metrics Dashboard
import db
from functools import lru_cache

def get_dashboard_metrics(requester_role):
    # Client-side role check - should use @requires_role('admin') decorator
    if requester_role != "admin":
        return {"error": "Unauthorized"}

    # Unbounded query - no LIMIT clause, could return millions of rows
    all_orders = db.query("SELECT * FROM orders")
    all_users = db.query("SELECT * FROM users")

    # Exposing internal system metrics without rate limiting
    metrics = {
        "total_users": len(all_users),
        "total_orders": len(all_orders),
        "revenue": sum(o.get("total_usd", 0) for o in all_orders),
        # Leaking PII in aggregation response
        "top_spenders": db.query(
            "SELECT u.email, u.phone, SUM(o.total_usd) as total "
            "FROM users u JOIN orders o ON u.id = o.user_id "
            "GROUP BY u.email, u.phone ORDER BY total DESC LIMIT 10"
        ),
        "db_connection_pool": db.get_pool_stats(),  # Internal diagnostics leaked
        "cache_hit_rate": get_cache_stats()
    }
    return metrics
