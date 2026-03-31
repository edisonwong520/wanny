from django.core.management.base import BaseCommand

from accounts.models import Account
from utils.logger import logger

from providers.services import MijiaAuthService


class Command(BaseCommand):
    help = "通过米家二维码登录并将授权数据同步到 PlatformAuth"

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            dest="email",
            required=True,
            help="指定需要绑定米家授权的账户邮箱。",
        )
        parser.add_argument(
            "--auth-file",
            dest="auth_file",
            default=None,
            help="可选：指定米家 auth.json 的本地路径。",
        )

    def handle(self, *args, **options):
        logger.info("========== Xiaomi Auth 登录开始 ==========")
        account = Account.objects.filter(email=options.get("email")).first()
        if not account:
            self.stderr.write(self.style.ERROR(f"Account not found: {options.get('email')}"))
            return

        auth_obj = MijiaAuthService.login_and_store(
            account=account,
            auth_file_path=options.get("auth_file"),
        )
        payload_keys = sorted((auth_obj.auth_payload or {}).keys())

        self.stdout.write(
            self.style.SUCCESS(
                f"Xiaomi authorization saved to PlatformAuth for {account.email}. payload_keys={payload_keys}"
            )
        )
