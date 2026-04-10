from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse

from accounts.auth import AccountTokenError, authenticate_account_token


class AccountAuthenticationMiddleware(MiddlewareMixin):
    """
    轻量级账户鉴权中间件。
    通过校验 Authorization: Bearer <token> 来识别当前请求所属的账户。
    并将 Account 实例注入到 request.account 中供后续视图使用。
    """
    def process_request(self, request):
        # 排除无需鉴权的路径（如登录、注册、健康检查等）
        exempt_urls = [
            '/api/accounts/login/',
            '/api/accounts/register/',
        ]
        
        if any(request.path.startswith(url) for url in exempt_urls):
            return None

        request.account = None

        auth_header = request.headers.get("Authorization", "")
        scheme, _, token = auth_header.partition(" ")

        if scheme.lower() != "bearer" or not token.strip():
            return None

        try:
            request.account = authenticate_account_token(token.strip())
        except AccountTokenError as exc:
            return JsonResponse({"error": str(exc)}, status=401)

        return None
