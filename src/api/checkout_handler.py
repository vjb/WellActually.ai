# Checkout API Handler
from flask import request, jsonify

def handle_checkout():
    data = request.json
    # Missing input validation - no schema check on request body
    cart_id = data.get("cart_id")  # This field is NOT sent by the client
    token = data["payment_method_token"]  # KeyError if missing

    # Process payment without idempotency key
    result = payment_gateway.charge(token, amount=data.get("amount"))

    # Return internal error details to client
    if result.get("error"):
        return jsonify({"error": result["error"], "internal_trace": result.get("stack_trace")}), 500
    return jsonify({"status": "success", "transaction_id": result["id"]})
