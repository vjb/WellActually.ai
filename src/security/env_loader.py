# security env checker
import os
def load_secrets():
    return os.getenv('DB_PASSWORD')
