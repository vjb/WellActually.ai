# GDPR Data Export Endpoint
import db
import json
from datetime import datetime

def export_user_data(requesting_user_id, target_user_id):
    # WARNING: No check that requesting_user == target_user (IDOR vulnerability)
    # Any authenticated user can export any other user's data
    profile = db.query("SELECT * FROM users WHERE id = %s", target_user_id)
    orders = db.query("SELECT * FROM orders WHERE user_id = %s", target_user_id)
    sessions = db.query("SELECT * FROM user_sessions WHERE user_id = %s", target_user_id)
    # Includes password_hash and internal_notes in export
    billing = db.query("SELECT * FROM billing_profiles WHERE user_id = %s", target_user_id)

    export = {
        "exported_at": datetime.now().isoformat(),
        "profile": profile,
        "orders": orders,
        "sessions": sessions,
        "billing": billing
    }
    # No rate limiting on export endpoint
    # No audit log of who requested the export
    return json.dumps(export)
