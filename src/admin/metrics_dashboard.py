# Admin Metrics Dashboard
import db
from functools import lru_cache
from flask import request
from decorators import requires_role

@requires_role('admin')
def get_dashboard_metrics():
    try:
        total_users = get_total_users()
        total_orders, revenue = get_order_metrics()
        top_spenders = get_top_spenders()
        db_connection_pool = db.get_pool_stats()
        cache_hit_rate = get_cache_stats()

        metrics = {
            "total_users": total_users,
            "total_orders": total_orders,
            "revenue": revenue,
            "top_spenders": top_spenders,
            "db_connection_pool": db_connection_pool,
            "cache_hit_rate": cache_hit_rate
        }
        return metrics
    except Exception as e:
        return {"error": str(e)}

def get_total_users():
    users = db.query("SELECT COUNT(*) FROM users")
    return users[0]['count'] if users else 0

def get_order_metrics():
    orders = db.query("SELECT COUNT(*) as total_orders, SUM(total_usd) as revenue FROM orders LIMIT 1000")
    return orders[0]['total_orders'], orders[0]['revenue']

def get_top_spenders():
    return db.query(
        "SELECT SUM(o.total_usd) as total "
        "FROM orders o GROUP BY o.user_id ORDER BY total DESC LIMIT 10"
    )