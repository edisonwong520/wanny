from django.db import models

class PendingCommand(models.Model):
    """
    用于 Manual-Gate 机制：存储用户在微信等代理端提出复杂请求后，
    系统解析生成的等待手动审批(approve)的 Shell 指令。
    """
    # 发起请求的用户唯一标识 (例如微信的 OpenID 或内部 User ID)
    user_id = models.CharField(max_length=255, db_index=True, verbose_name="Requester ID")
    
    # 原始聊天意图
    original_prompt = models.TextField(verbose_name="Original User Prompt")
    
    # AI 帮忙生成的底层 Shell 或 Gemini 代理指令
    shell_command = models.TextField(verbose_name="Generated Command to Run")
    
    # 指令等待状态
    is_approved = models.BooleanField(default=False, verbose_name="Is Approved")
    is_executed = models.BooleanField(default=False, verbose_name="Is Executed")
    is_cancelled = models.BooleanField(default=False, verbose_name="Is Cancelled", help_text="服务重启时自动软删除残留的僵尸工单")
    
    # 额外存储 UI 显示需要的丰富元数据 (由 AI 生成/解析)
    metadata = models.JSONField(default=dict, blank=True, verbose_name="Rich Metadata")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    
    class Meta:
        db_table = "comms_pending_command"
        ordering = ['-created_at']
        verbose_name = "Pending Command"
        verbose_name_plural = "Pending Commands"

    def __str__(self):
        return f"User {self.user_id} - Cmd: {self.shell_command[:30]}"
