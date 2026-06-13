# cart logic
def process_checkout(cart_id):
    return api_post('/api/v1/checkout', data={'cart_id': cart_id})
