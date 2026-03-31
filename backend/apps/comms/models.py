from django.db import models

class Mission(models.Model):
    """
    任务模型 (Mission / Task)。
    存储由系统解析用户意图、监控异常或后台扫描生成的各类执行单元。
    具有生命周期状态流转（待审批 -> 已通过/已拒绝 -> 执行成功/失败）。
    """
    class StatusChoices(models.TextChoices):
        PENDING = 'pending', '待审批'
        APPROVED = 'approved', '已通过'
        REJECTED = 'rejected', '已拒绝'
        FAILED = 'failed', '执行失败'
        CANCELLED = 'cancelled', '已作废'

    # 账户关联 (租户隔离)
    account = models.ForeignKey(
        'accounts.Account', 
        on_delete=models.CASCADE, 
        related_name='missions',
        null=True,
        blank=True,
        verbose_name="所属账户"
    )

    # 发起请求的用户唯一标识 (例如微信 OpenID)
    user_id = models.CharField(max_length=255, db_index=True, verbose_name="发起人标识")
    
    # 任务状态
    status = models.CharField(
        max_length=20, 
        choices=StatusChoices.choices, 
        default=StatusChoices.PENDING, 
        verbose_name="任务状态"
    )

    # 原始聊天内容或触发原因
    original_prompt = models.TextField(verbose_name="原始输入/触发详情")
    
    # AI 编排后的底层执行指令或 Shell 命令
    shell_command = models.TextField(blank=True, verbose_name="后端指令/脚本")
    
    # 额外存储 UI 显示需要的丰富元数据 (由 AI 生成/解析)
    # 包含：title, summary, risk, plan, context, suggested_reply 等
    metadata = models.JSONField(default=dict, blank=True, verbose_name="任务元数据")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    
    class Meta:
        db_table = "comms_mission"
        ordering = ['-created_at']
        verbose_name = "任务"
        verbose_name_plural = "任务"

    def __str__(self):
        return f"Mission {self.id} ({self.get_status_display()}) - User: {self.user_id}"
