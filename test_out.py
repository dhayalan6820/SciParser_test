import secrets

JWT_SECRET_KEY = secrets.token_hex(32)
print(JWT_SECRET_KEY)