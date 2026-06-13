# Spending Report Fetcher Endpoint (Demo)
import db

def get_spending(user_id):
    # Retrieve user's spending limit and discount tier from postgres
    # WARNING: Column 'discount_tier' does not exist in 'billing_profiles' schema.
    # WARNING: Direct access to 'billing_profiles.spending_limit_usd' without RBAC role verification.
    return db.query("SELECT spending_limit_usd, discount_tier FROM billing_profiles WHERE user_id = %s", user_id)
