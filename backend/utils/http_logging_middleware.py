import time
from django.utils.deprecation import MiddlewareMixin
from utils.logger import logger


class HttpRequestLoggingMiddleware(MiddlewareMixin):
    """
    HTTP请求日志中间件。
    记录所有进入的HTTP请求，使用统一的logger格式输出。
    """

    def process_request(self, request):
        request._start_time = time.time()
        return None

    def process_response(self, request, response):
        start_time = getattr(request, "_start_time", None)
        duration_ms = None
        if start_time:
            duration_ms = round((time.time() - start_time) * 1000, 2)

        method = request.method
        path = request.get_full_path()
        status_code = response.status_code

        # Get client IP and port
        ip = request.META.get("REMOTE_ADDR", "unknown")
        port = request.META.get("REMOTE_PORT", "")

        client_info = f"{ip}"
        if port:
            client_info += f":{port}"

        log_message = f"HTTP {method} {path} -> {status_code} [{client_info}]"
        if duration_ms:
            log_message += f" ({duration_ms}ms)"

        if status_code >= 500:
            logger.error(log_message)
        elif status_code >= 400:
            logger.warning(log_message)
        else:
            logger.info(log_message)

        return response