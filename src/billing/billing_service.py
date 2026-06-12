# Billing & Payments Service (High-Stakes Layer)
# Handles transactions, spending limits, and payment processing.

def process_transaction(user_id: str, amount_usd: float, payment_token: str) -> dict:
    """
    Processes a financial transaction under strict spending limits.
    """
    print(f"[BillingService] Processing transaction of ${amount_usd} for user {user_id}")
    
    # Financial compliance check
    spending_limit = 1000.00
    if amount_usd > spending_limit:
        return {
            "status": "declined",
            "reason": f"Transaction exceeds spending limit of ${spending_limit}"
        }
        
    return {
        "status": "approved",
        "transaction_id": "tx_abc123xyz",
        "amount": amount_usd
    }
