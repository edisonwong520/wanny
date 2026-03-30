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

    user_id = models.CharField(max_length=255, db_index=True, verbose_name="User ID")
    category = models.CharField(
        max_length=50,
        choices=CategoryChoices.choices,
        default=CategoryChoices.OTHER,
        verbose_name="Category"
    )
    key = models.CharField(max_length=255, verbose_name="Preference Key",
                           help_text="偏好键，如 preferred_temp, bedtime_routine")
    value = models.TextField(verbose_name="Preference Value",
                             help_text="偏好值，如 24, 23:00")
    confidence = models.FloatField(default=0.5, verbose_name="Confidence",
                                   help_text="置信度 0.0 - 1.0")
    last_confirmed = models.DateTimeField(null=True, blank=True, verbose_name="Last Confirmed",
                                          help_text="上次用户确认的时间")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "memory_user_profile"
        unique_together = ['user_id', 'key']
        ordering = ['-confidence', '-updated_at']
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

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

    user_id = models.CharField(max_length=255, db_index=True, verbose_name="User ID")
    message = models.TextField(verbose_name="Push Message")
    feedback = models.CharField(
        max_length=20,
        choices=FeedbackChoices.choices,
        default=FeedbackChoices.PENDING,
        verbose_name="User Feedback"
    )
    score = models.FloatField(default=0.0, verbose_name="Impact Score",
                              help_text="推送时的评分：环境紧急度 × 画像匹配度 × 反馈权重")
    source = models.CharField(max_length=100, default="daily_review", verbose_name="Source",
                              help_text="触发来源：daily_review, monitor, manual")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "memory_proactive_log"
        ordering = ['-created_at']
        verbose_name = "Proactive Log"
        verbose_name_plural = "Proactive Logs"

    def __str__(self):
        return f"[{self.feedback}] {self.message[:50]}... (score={self.score})"
