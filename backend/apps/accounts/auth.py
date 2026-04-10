from django.conf import settings
from django.core import signing

from accounts.models import Account


ACCOUNT_TOKEN_SALT = "wanny.accounts.account-token"
DEFAULT_ACCOUNT_TOKEN_MAX_AGE_SECONDS = 60 * 60 * 24 * 30


class AccountTokenError(Exception):
    """Raised when an account bearer token cannot be authenticated."""


def create_account_token(account: Account) -> str:
    return signing.dumps(
        {
            "account_id": account.id,
            "email": account.email,
        },
        salt=ACCOUNT_TOKEN_SALT,
    )


def authenticate_account_token(token: str) -> Account:
    max_age = getattr(
        settings,
        "WANNY_ACCOUNT_TOKEN_MAX_AGE_SECONDS",
        DEFAULT_ACCOUNT_TOKEN_MAX_AGE_SECONDS,
    )

    try:
        payload = signing.loads(token, salt=ACCOUNT_TOKEN_SALT, max_age=max_age)
    except signing.SignatureExpired as exc:
        raise AccountTokenError("账户会话已过期") from exc
    except signing.BadSignature as exc:
        raise AccountTokenError("无效的账户会话") from exc

    account_id = payload.get("account_id")
    email = payload.get("email")
    if not account_id or not email:
        raise AccountTokenError("无效的账户会话")

    try:
        return Account.objects.get(id=account_id, email=email)
    except Account.DoesNotExist as exc:
        raise AccountTokenError("账户不存在或会话已过期") from exc
