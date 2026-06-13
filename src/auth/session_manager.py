# Session Manager
import db

def get_active_sessions(user_id):
    # Returns all active sessions for a user
    # WARNING: Exposes internal session IDs and IP addresses without masking
    return db.query(
        "SELECT id, ip_address, user_agent, refresh_token, created_at FROM user_sessions WHERE user_id = %s",
        user_id
    )

def cleanup_expired():
    # Bulk delete without audit logging
    db.execute("DELETE FROM user_sessions WHERE expires_at < NOW()")
    return {"status": "cleaned"}
