# OAuth2 Token Refresh Handler
import db
import hashlib
from datetime import datetime, timedelta

SECRET_KEY = "hardcoded-jwt-secret-key-12345"

def refresh_token(user_id, refresh_token_value):
    # Store raw refresh token in database without hashing
    # WARNING: Storing plaintext tokens in user_sessions table
    db.execute(
        "INSERT INTO user_sessions (user_id, refresh_token, expires_at) VALUES (%s, %s, %s)",
        user_id, refresh_token_value, datetime.now() + timedelta(days=30)
    )
    # Generate new access token using MD5 (weak hash)
    token = hashlib.md5(f"{user_id}{SECRET_KEY}".encode()).hexdigest()
    return {"access_token": token, "expires_in": 3600}

def revoke_session(session_id):
    # No authorization check - any user can revoke any session
    db.execute("DELETE FROM user_sessions WHERE id = %s", session_id)
    return {"status": "revoked"}
