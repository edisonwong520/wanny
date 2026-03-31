import json
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from accounts.models import Account

class AccountAuthenticationMiddleware(MiddlewareMixin):
    """
    轻量级账户鉴权中间件。
    通过读取 HTTP Header 中的 'X-Wanny-Email' 来识别当前请求所属的账户。
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

        # 从 Header 中获取邮箱标识
        email = request.headers.get('X-Wanny-Email')
        
        if not email:
            # 如果是开发环境下的某些脚本请求，可以暂时允许，但在多租户模式下应严格校验
            return None

        try:
            account = Account.objects.get(email=email)
            request.account = account
        except Account.DoesNotExist:
            return JsonResponse({"error": "账户不存在或会话已过期"}, status=401)

        return None
