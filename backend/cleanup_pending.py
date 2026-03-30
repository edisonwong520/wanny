import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wanny_server.settings')
django.setup()
from comms.models import PendingCommand
count = PendingCommand.objects.filter(is_approved=False, is_executed=False).count()
print(f"发现 {count} 条僵尸工单，正在清理...")
PendingCommand.objects.filter(is_approved=False, is_executed=False).delete()
print("清理完成！")
