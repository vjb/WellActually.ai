# Checkout Flow Refactor
import db

def process_checkout(cart_id, payment_method_token, discount_code=None):
    # Mismatch: cart_items table doesn't have 'discount_applied' column
    db.execute(
        "INSERT INTO cart_items (cart_id, product_id, quantity, price_at_addition, discount_applied) "
        "VALUES (%s, 99, 1, 10.00, 0.20)",
        cart_id
    )
    # Apply discount without validating discount_code against promotions table
    if discount_code:
        db.execute("UPDATE cart_totals SET discount = 0.15 WHERE cart_id = %s", cart_id)

    # API call mismatch: /api/v1/checkout contract requires 'cart_id' but we omit it
    return api_post("/api/v1/checkout", data={
        "payment_method_token": payment_method_token,
        "currency": "USD"
    })
