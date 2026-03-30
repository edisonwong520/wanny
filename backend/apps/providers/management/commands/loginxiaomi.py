from django.core.management.base import BaseCommand

from utils.logger import logger

from providers.services import XiaomiAuthService


class Command(BaseCommand):
    help = "通过米家二维码登录并将授权数据同步到 PlatformAuth"

    def add_arguments(self, parser):
        parser.add_argument(
            "--auth-file",
            dest="auth_file",
            default=None,
            help="可选：指定米家 auth.json 的本地路径。",
        )

    def handle(self, *args, **options):
        logger.info("========== Xiaomi Auth 登录开始 ==========")
        auth_obj = XiaomiAuthService.login_and_store(auth_file_path=options.get("auth_file"))
        payload_keys = sorted((auth_obj.auth_payload or {}).keys())

        self.stdout.write(
            self.style.SUCCESS(
                f"Xiaomi authorization saved to PlatformAuth. payload_keys={payload_keys}"
            )
        )
