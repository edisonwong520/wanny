from django.db import IntegrityError, models
from django.db.models import Q

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

    class SourceTypeChoices(models.TextChoices):
        SHELL = 'shell', 'Shell 指令'
        DEVICE_CONTROL = 'device_control', '设备控制'
        DEVICE_CLARIFICATION = 'device_clarification', '设备澄清'

    source_type = models.CharField(
        max_length=32,
        choices=SourceTypeChoices.choices,
        default=SourceTypeChoices.SHELL,
        verbose_name="任务来源类型"
    )

    device_id = models.CharField(max_length=128, blank=True, verbose_name="目标设备 ID")
    control_id = models.CharField(max_length=255, blank=True, verbose_name="目标控制 ID")
    control_key = models.CharField(max_length=64, blank=True, verbose_name="控制项标识")
    operation_action = models.CharField(max_length=32, blank=True, verbose_name="操作动作")
    operation_value = models.JSONField(default=dict, blank=True, verbose_name="操作目标值")
    
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


class DeviceOperationContext(models.Model):
    """
    用户最近的设备操作上下文，用于承接连续调节类命令。
    """
    account = models.ForeignKey(
        'accounts.Account',
        on_delete=models.CASCADE,
        related_name='device_operation_contexts',
        verbose_name="所属账户"
    )
    platform_user_id = models.CharField(max_length=255, blank=True, db_index=True, verbose_name="发起人标识")
    device = models.ForeignKey(
        'devices.DeviceSnapshot',
        on_delete=models.CASCADE,
        related_name='operation_contexts',
        verbose_name="目标设备"
    )
    control_id = models.CharField(max_length=255, blank=True, verbose_name="目标控制 ID")
    control_key = models.CharField(max_length=64, verbose_name="控制项标识")
    operation_type = models.CharField(max_length=32, verbose_name="操作类型")
    value = models.JSONField(default=dict, blank=True, verbose_name="操作值")
    raw_user_msg = models.TextField(blank=True, verbose_name="原始用户消息")
    normalized_msg = models.TextField(blank=True, verbose_name="归一化消息")
    voice_transcript = models.TextField(blank=True, verbose_name="语音转写文本")
    intent_json = models.JSONField(default=dict, blank=True, verbose_name="意图解析结果")
    resolver_result = models.JSONField(default=dict, blank=True, verbose_name="设备解析结果")
    execution_result = models.JSONField(default=dict, blank=True, verbose_name="执行结果")
    operated_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="操作时间")

    class Meta:
        db_table = "comms_device_context"
        ordering = ['-operated_at']
        verbose_name = "设备操作上下文"
        verbose_name_plural = "设备操作上下文"

    def __str__(self):
        return f"{self.account_id}:{self.device_id}:{self.control_key}"

class ChatMessage(models.Model):
    """
    通用对话消息记录表。
    记录用户与 AI 之间的每一次沟通细节（WeChat, API 等）。
    """
    class RoleChoices(models.TextChoices):
        USER = 'user', '用户'
        ASSISTANT = 'assistant', '助手'
        SYSTEM = 'system', '系统'

    # 账户关联
    account = models.ForeignKey(
        'accounts.Account',
        on_delete=models.CASCADE,
        related_name='chat_messages',
        null=True,
        blank=True,
        verbose_name="所属账户"
    )

    # 发起者唯一标识 (例如微信 OpenID)
    platform_user_id = models.CharField(max_length=255, db_index=True, verbose_name="发起人标识")

    linked_device_context = models.ForeignKey(
        'comms.DeviceOperationContext',
        on_delete=models.SET_NULL,
        related_name='linked_chat_messages',
        null=True,
        blank=True,
        verbose_name="关联设备上下文",
    )
    
    # 消息来源平台标识 (wechat, api, etc.)
    source = models.CharField(max_length=50, default='wechat', verbose_name="来源平台")

    role = models.CharField(
        max_length=20,
        choices=RoleChoices.choices,
        default=RoleChoices.USER,
        verbose_name="角色"
    )

    content = models.TextField(verbose_name="消息内容")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="发送时间")

    class Meta:
        db_table = "comms_chat_message"
        ordering = ['-created_at']
        verbose_name = "对话记录"
        verbose_name_plural = "对话记录"

    def __str__(self):
        return f"[{self.get_role_display()}] {self.content[:30]}... ({self.platform_user_id})"


class LearnedKeyword(models.Model):
    """
    动态学习得到的关键词映射。
    account 为空表示全局关键词；否则为用户私有关键词。
    """

    class CategoryChoices(models.TextChoices):
        DEVICE = "device", "设备"
        ROOM = "room", "房间"
        CONTROL = "control", "控制项"
        ACTION = "action", "动作"
        COLLOQUIAL = "colloquial", "口语化"

    class SourceChoices(models.TextChoices):
        HISTORY = "history", "历史对话"
        DEVICE = "device", "设备数据库"
        USER = "user", "用户自定义"
        SYSTEM = "system", "系统预置"

    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        related_name="learned_keywords",
        null=True,
        blank=True,
        verbose_name="所属账户",
    )
    keyword = models.CharField(max_length=64, verbose_name="原始关键词")
    normalized_keyword = models.CharField(max_length=64, db_index=True, verbose_name="归一化关键词")
    canonical = models.CharField(max_length=64, blank=True, verbose_name="标准映射")
    canonical_payload = models.JSONField(default=dict, blank=True, verbose_name="结构化映射")
    category = models.CharField(max_length=24, choices=CategoryChoices.choices, verbose_name="关键词分类")
    source = models.CharField(max_length=24, choices=SourceChoices.choices, verbose_name="关键词来源")
    confidence = models.FloatField(default=0.5, verbose_name="置信度")
    usage_count = models.IntegerField(default=1, verbose_name="使用次数")
    last_used_at = models.DateTimeField(null=True, blank=True, verbose_name="最后使用时间")
    learned_at = models.DateTimeField(auto_now_add=True, verbose_name="学习时间")
    is_active = models.BooleanField(default=True, verbose_name="是否启用")

    class Meta:
        db_table = "comms_learned_keyword"
        ordering = ["account_id", "category", "-confidence", "-usage_count", "normalized_keyword"]
        verbose_name = "学习关键词"
        verbose_name_plural = "学习关键词"
        constraints = [
            models.UniqueConstraint(
                fields=["account", "normalized_keyword", "category"],
                condition=Q(account__isnull=False),
                name="uniq_learned_keyword_account",
            ),
            models.UniqueConstraint(
                fields=["normalized_keyword", "category"],
                condition=Q(account__isnull=True),
                name="uniq_learned_keyword_global",
            ),
        ]

    def __str__(self):
        scope = f"account={self.account_id}" if self.account_id else "global"
        return f"{scope}:{self.category}:{self.keyword}->{self.canonical or '-'}"

    def save(self, *args, **kwargs):
        duplicate_query = LearnedKeyword.objects.filter(
            normalized_keyword=self.normalized_keyword,
            category=self.category,
            is_active=True,
        )
        if self.pk:
            duplicate_query = duplicate_query.exclude(pk=self.pk)
        if self.account_id:
            duplicate_query = duplicate_query.filter(account_id=self.account_id)
        else:
            duplicate_query = duplicate_query.filter(account__isnull=True)
        if duplicate_query.exists():
            raise IntegrityError("Duplicate learned keyword in the same scope is not allowed.")
        return super().save(*args, **kwargs)
