from django.db import models


class InspectionRule(models.Model):
    class RuleTypeChoices(models.TextChoices):
        MAINTENANCE = "maintenance", "保养"
        HEALTH = "health", "健康"
        CUSTOM = "custom", "自定义"

    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        related_name="inspection_rules",
        null=True,
        blank=True,
        verbose_name="所属账户",
    )
    rule_type = models.CharField(max_length=24, choices=RuleTypeChoices.choices, verbose_name="规则类型")
    system_key = models.CharField(max_length=64, blank=True, db_index=True, verbose_name="系统规则键")
    device_category = models.CharField(max_length=64, blank=True, verbose_name="设备分类")
    name = models.CharField(max_length=128, verbose_name="规则名称")
    description = models.TextField(blank=True, verbose_name="规则说明")
    check_frequency = models.CharField(max_length=64, default="hourly", verbose_name="检查频率")
    condition_spec = models.JSONField(default=dict, blank=True, verbose_name="条件规格")
    action_spec = models.JSONField(default=dict, blank=True, verbose_name="建议动作")
    suggestion_template = models.TextField(blank=True, verbose_name="建议模板")
    priority = models.PositiveSmallIntegerField(default=5, verbose_name="基础优先级")
    cooldown_hours = models.PositiveIntegerField(default=24, verbose_name="冷却小时数")
    is_system_default = models.BooleanField(default=False, verbose_name="是否系统规则")
    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "care_inspection_rule"
        ordering = ["account_id", "-is_system_default", "name", "id"]
        verbose_name = "巡检规则"
        verbose_name_plural = "巡检规则"

    def __str__(self):
        return self.name


class ExternalDataSource(models.Model):
    class SourceTypeChoices(models.TextChoices):
        WEATHER_API = "weather_api", "天气 API"
        HA_ENTITY = "ha_entity", "HA 实体"
        OTHER = "other", "其他"

    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        related_name="external_data_sources",
        verbose_name="所属账户",
    )
    source_type = models.CharField(max_length=32, choices=SourceTypeChoices.choices, verbose_name="数据源类型")
    name = models.CharField(max_length=128, verbose_name="数据源名称")
    config = models.JSONField(default=dict, blank=True, verbose_name="配置")
    fetch_frequency = models.CharField(max_length=64, default="30m", verbose_name="获取频率")
    last_fetch_at = models.DateTimeField(null=True, blank=True, verbose_name="上次获取时间")
    last_data = models.JSONField(default=dict, blank=True, verbose_name="最新数据")
    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "care_external_data_source"
        ordering = ["account_id", "name", "id"]
        verbose_name = "外部数据源"
        verbose_name_plural = "外部数据源"

    def __str__(self):
        return self.name


class CareSuggestion(models.Model):
    class SuggestionTypeChoices(models.TextChoices):
        INSPECTION = "inspection", "主动巡检"
        CARE = "care", "人文关怀"

    class StatusChoices(models.TextChoices):
        PENDING = "pending", "待处理"
        APPROVED = "approved", "已采纳"
        REJECTED = "rejected", "已拒绝"
        IGNORED = "ignored", "已忽略"
        EXECUTED = "executed", "已执行"
        FAILED = "failed", "执行失败"

    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        related_name="care_suggestions",
        verbose_name="所属账户",
    )
    suggestion_type = models.CharField(max_length=24, choices=SuggestionTypeChoices.choices, verbose_name="建议类型")
    source_rule = models.ForeignKey(
        InspectionRule,
        on_delete=models.SET_NULL,
        related_name="suggestions",
        null=True,
        blank=True,
        verbose_name="来源规则",
    )
    device = models.ForeignKey(
        "devices.DeviceSnapshot",
        on_delete=models.SET_NULL,
        related_name="care_suggestions",
        null=True,
        blank=True,
        verbose_name="关联设备",
    )
    control_target = models.ForeignKey(
        "devices.DeviceControl",
        on_delete=models.SET_NULL,
        related_name="care_suggestions",
        null=True,
        blank=True,
        verbose_name="执行控制目标",
    )
    mission = models.ForeignKey(
        "comms.Mission",
        on_delete=models.SET_NULL,
        related_name="care_suggestions",
        null=True,
        blank=True,
        verbose_name="关联任务",
    )
    title = models.CharField(max_length=255, verbose_name="标题")
    body = models.TextField(verbose_name="详情")
    action_spec = models.JSONField(default=dict, blank=True, verbose_name="动作规格")
    priority = models.FloatField(default=0.0, verbose_name="优先级")
    status = models.CharField(max_length=24, choices=StatusChoices.choices, default=StatusChoices.PENDING, verbose_name="状态")
    dedupe_key = models.CharField(max_length=255, db_index=True, verbose_name="去重键")
    aggregated_count = models.PositiveIntegerField(default=1, verbose_name="聚合数量")
    aggregated_from = models.JSONField(default=list, blank=True, verbose_name="聚合来源")
    source_event = models.JSONField(default=dict, blank=True, verbose_name="来源事件")
    user_feedback = models.JSONField(default=dict, blank=True, verbose_name="用户反馈")
    feedback_collected_at = models.DateTimeField(null=True, blank=True, verbose_name="反馈时间")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "care_suggestion"
        ordering = ["-priority", "-created_at", "-id"]
        verbose_name = "关怀建议"
        verbose_name_plural = "关怀建议"

    def __str__(self):
        return self.title
