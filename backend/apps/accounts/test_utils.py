from accounts.auth import create_account_token


def auth_headers(account):
    return {"HTTP_AUTHORIZATION": f"Bearer {create_account_token(account)}"}
