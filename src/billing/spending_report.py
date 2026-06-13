# billing modifications
import db
def get_spending(user_id):
    return db.query('SELECT spending_limit_usd FROM billing_profiles WHERE user_id = %s', user_id)
