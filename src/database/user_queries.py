# User Data Queries
import db

def get_user_full_profile(user_id):
    # WARNING: SELECT * exposes password_hash, internal_notes, and ssn_last4
    return db.query("SELECT * FROM users WHERE id = %s", user_id)

def get_user_pii_fields(user_id):
    # Direct access to PII columns without RBAC check
    return db.query(
        "SELECT email, phone, address, ssn_last4, date_of_birth "
        "FROM users WHERE id = %s",
        user_id
    )
