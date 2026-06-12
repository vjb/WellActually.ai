# Cart Service (Presentation/Application Layer)
# Handles frontend checkout operations and cart items.

def add_item_to_cart(cart_id: str, product_id: str, quantity: int) -> dict:
    """
    Adds a product to the cart with specified quantity.
    """
    print(f"[CartService] Adding item {product_id} to cart {cart_id}")
    # Low-stakes database insert via mocked model
    return {
        "status": "success",
        "cart_id": cart_id,
        "product_id": product_id,
        "quantity": quantity
    }


def process_cart_checkout(cart_id: str, payment_method_token: str) -> dict:
    """
    Triggers the checkout process for the active cart.
    This coordinates with the billing and inventory services.
    """
    print(f"[CartService] Initiating checkout for cart {cart_id}")
    
    # OpenAPI contract compliance: checkout requires cart_id.
    # Note: If cart_id is missing, this would violate the OpenAPI schema.
    payload = {
        "cart_id": cart_id,
        "payment_method_token": payment_method_token
    }
    return payload
