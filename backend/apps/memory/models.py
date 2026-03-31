from django.db import models


class UserProfile(models.Model):
    """
    结构化用户画像 (Memory B - Core)。
    存储 Jarvis 从对话和行为中学习到的用户偏好，作为决策的高置信度准则。
    """
    class CategoryChoices(models.TextChoices):
        ENVIRONMENT = 'Environment', '环境偏好'
        ENTERTAINMENT = 'Entertainment', '娱乐偏好'
        HABIT = 'Habit', '日常习惯'
        DEVICE = 'Device', '设备偏好'
        OTHER = 'Other', '其他'

    class SourceChoices(models.TextChoices):
        REVIEW = 'review', '定时复盘'
        MANUAL = 'manual', '用户手动修改'

    account = models.ForeignKey('accounts.Account', on_delete=models.CASCADE, verbose_name="关联账户", db_index=True)
    category = models.CharField(
        max_length=50,
        choices=CategoryChoices.choices,
        default=CategoryChoices.OTHER,
        verbose_name="类别"
    )
    key = models.CharField(max_length=255, verbose_name="偏好键",
                           help_text="偏好键，如 preferred_temp, bedtime_routine")
    value = models.TextField(verbose_name="偏好值",
                             help_text="偏好值，如 24, 23:00")
    confidence = models.FloatField(default=0.5, verbose_name="置信度",
                                   help_text="置信度 0.0 - 1.0")
    source = models.CharField(
        max_length=20,
        choices=SourceChoices.choices,
        default=SourceChoices.REVIEW,
        verbose_name="来源",
        help_text="当前画像值的来源：定时复盘或用户手动修改"
    )
    is_user_edited = models.BooleanField(
        default=False,
        verbose_name="是否为用户编辑",
        help_text="是否由用户手动修改；若为 True，后续复盘应优先保留该值"
    )
    last_confirmed = models.DateTimeField(null=True, blank=True, verbose_name="上次确认时间",
                                          help_text="上次用户确认的时间")
    last_review_value = models.TextField(
        blank=True,
        default="",
        verbose_name="上次复盘建议值",
        help_text="当用户手动修改后，最近一次定时复盘建议的值会记录在这里，供后续融合或审计"
    )
    last_review_confidence = models.FloatField(
        null=True,
        blank=True,
        verbose_name="上次复盘置信度",
        help_text="最近一次复盘建议的置信度"
    )
    last_review_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="上次复盘时间",
        help_text="最近一次复盘处理该画像的时间"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "memory_user_profile"
        unique_together = ['account', 'key']
        ordering = ['-confidence', '-updated_at']
        verbose_name = "用户画像"
        verbose_name_plural = "用户画像"

    def __str__(self):
        return f"[{self.category}] {self.key}={self.value} (conf={self.confidence})"


class ProactiveLog(models.Model):
    """
    主动推送日志，记录 Jarvis 每一次主动关怀推送的内容和用户反馈。
    用于后续优化推送算法的评分权重。
    """
    class FeedbackChoices(models.TextChoices):
        APPROVED = 'APPROVED', '已采纳'
        DENIED = 'DENIED', '已拒绝'
        IGNORED = 'IGNORED', '已忽略'
        PENDING = 'PENDING', '等待反馈'

    account = models.ForeignKey('accounts.Account', on_delete=models.CASCADE, verbose_name="关联账户", db_index=True)
    message = models.TextField(verbose_name="推送消息")
    feedback = models.CharField(
        max_length=20,
        choices=FeedbackChoices.choices,
        default=FeedbackChoices.PENDING,
        verbose_name="用户反馈"
    )
    score = models.FloatField(default=0.0, verbose_name="影响分",
                              help_text="推送时的评分：环境紧急度 × 画像匹配度 × 反馈权重")
    source = models.CharField(max_length=100, default="daily_review", verbose_name="来源",
                              help_text="触发来源：daily_review, monitor, manual")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = "memory_proactive_log"
        ordering = ['-created_at']
        verbose_name = "主动关怀日志"
        verbose_name_plural = "主动关怀日志"

    def __str__(self):
        return f"[{self.feedback}] {self.message[:50]}... (score={self.score})"
