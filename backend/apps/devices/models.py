from django.db import models


class DeviceDashboardState(models.Model):
    """
    设备总览页面的全局状态，用于追踪后台同步进度、触发源与最近刷新时间。
    """
    # 账户关联
    account = models.ForeignKey(
        'accounts.Account',
        on_delete=models.CASCADE,
        related_name='dashboard_states',
        null=True,
        blank=True,
        verbose_name="所属账户"
    )
    key = models.CharField(max_length=32, default="default", verbose_name="状态标识")
    source = models.CharField(max_length=32, default="none", verbose_name="数据来源")
    last_trigger = models.CharField(max_length=32, default="bootstrap", verbose_name="上次触发行为")
    requested_trigger = models.CharField(max_length=32, blank=True, default="", verbose_name="正在请求的触发行为")
    refresh_requested_at = models.DateTimeField(null=True, blank=True, verbose_name="请求刷新时间")
    last_error = models.TextField(blank=True, verbose_name="上次错误信息")
    refreshed_at = models.DateTimeField(null=True, blank=True, verbose_name="最近成功刷新时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "devices_dashboard_state"
        unique_together = ('account', 'key')
        verbose_name = "设备总览状态"
        verbose_name_plural = "设备总览状态"

    def __str__(self):
        return f"{self.key} ({self.source})"


class DeviceRoom(models.Model):
    """
    米家房间模型，用于前端按空间维度对设备进行分组展现。
    """
    # 账户关联
    account = models.ForeignKey(
        'accounts.Account',
        on_delete=models.CASCADE,
        related_name='rooms',
        null=True,
        blank=True,
        verbose_name="所属账户"
    )
    slug = models.SlugField(max_length=64, verbose_name="房间标识")
    name = models.CharField(max_length=64, verbose_name="房间名称")
    climate = models.CharField(max_length=128, blank=True, verbose_name="环境概览文字", help_text="如 '26°C / 58% RH'")
    summary = models.TextField(blank=True, verbose_name="房间摘要描述")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="排序权重")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "devices_room"
        unique_together = ('account', 'slug')
        ordering = ["sort_order", "id"]
        verbose_name = "设备房间"
        verbose_name_plural = "设备房间"

    def __str__(self):
        return self.name


class DeviceSnapshot(models.Model):
    """
    设备状态快照，存储从米家接口拉取的设备基础信息与实时遥测数据。
    """
    class StatusChoices(models.TextChoices):
        ONLINE = "online", "在线"
        ATTENTION = "attention", "需留意"
        OFFLINE = "offline", "离线"

    # 账户关联
    account = models.ForeignKey(
        'accounts.Account',
        on_delete=models.CASCADE,
        related_name='device_snapshots',
        null=True,
        blank=True,
        verbose_name="所属账户"
    )
    # 米家原始设备 ID (did)
    external_id = models.CharField(max_length=128, verbose_name="外部设备 ID")
    room = models.ForeignKey(
        DeviceRoom,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="devices",
        verbose_name="关联房间"
    )
    name = models.CharField(max_length=128, verbose_name="设备名称")
    category = models.CharField(max_length=64, verbose_name="设备类型")
    status = models.CharField(
        max_length=16,
        choices=StatusChoices.choices,
        default=StatusChoices.ONLINE,
        verbose_name="在线状态"
    )
    telemetry = models.CharField(max_length=255, blank=True, verbose_name="遥测摘要", help_text="如 '已开启 / 68% 亮度'")
    note = models.TextField(blank=True, verbose_name="系统备注")
    capabilities = models.JSONField(default=list, blank=True, verbose_name="可用能力列表")
    last_seen = models.DateTimeField(null=True, blank=True, verbose_name="最近活动时间")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="排序权重")
    source_payload = models.JSONField(default=dict, blank=True, verbose_name="原始数据报文")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "devices_snapshot"
        unique_together = ('account', 'external_id')
        ordering = ["sort_order", "id"]
        verbose_name = "设备快照"
        verbose_name_plural = "设备快照"

    def __str__(self):
        return self.name


class DeviceControl(models.Model):
    """
    设备控制节点/子功能表。
    用于承接 HA 的 entity、米家的属性/动作等细粒度能力，供前端进入单设备后渲染专属控制面板。
    """

    class KindChoices(models.TextChoices):
        SENSOR = "sensor", "传感器"
        TOGGLE = "toggle", "开关"
        RANGE = "range", "范围控制"
        ENUM = "enum", "枚举控制"
        ACTION = "action", "动作"
        TEXT = "text", "文本"

    class SourceTypeChoices(models.TextChoices):
        HA_ENTITY = "ha_entity", "Home Assistant 实体"
        MIJIA_PROPERTY = "mijia_property", "米家属性"
        MIJIA_ACTION = "mijia_action", "米家动作"
        MIDEA_CLOUD_PROPERTY = "midea_cloud_property", "美的属性"
        MIDEA_CLOUD_ACTION = "midea_cloud_action", "美的动作"

    account = models.ForeignKey(
        'accounts.Account',
        on_delete=models.CASCADE,
        related_name='device_controls',
        null=True,
        blank=True,
        verbose_name="所属账户"
    )
    device = models.ForeignKey(
        DeviceSnapshot,
        on_delete=models.CASCADE,
        related_name="controls",
        verbose_name="所属设备"
    )
    external_id = models.CharField(max_length=255, verbose_name="外部控制 ID")
    parent_external_id = models.CharField(max_length=255, blank=True, verbose_name="父级控制 ID")
    source_type = models.CharField(
        max_length=32,
        choices=SourceTypeChoices.choices,
        verbose_name="来源类型"
    )
    kind = models.CharField(
        max_length=16,
        choices=KindChoices.choices,
        default=KindChoices.SENSOR,
        verbose_name="控制类型"
    )
    key = models.CharField(max_length=128, verbose_name="控制标识")
    label = models.CharField(max_length=128, verbose_name="控制名称")
    group_label = models.CharField(max_length=128, blank=True, verbose_name="分组名称")
    writable = models.BooleanField(default=False, verbose_name="是否可写")
    value = models.JSONField(default=dict, blank=True, verbose_name="当前值")
    unit = models.CharField(max_length=32, blank=True, verbose_name="单位")
    options = models.JSONField(default=list, blank=True, verbose_name="可选项")
    range_spec = models.JSONField(default=dict, blank=True, verbose_name="范围规格")
    action_params = models.JSONField(default=dict, blank=True, verbose_name="动作参数")
    source_payload = models.JSONField(default=dict, blank=True, verbose_name="原始数据报文")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="排序权重")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "devices_control"
        unique_together = ('account', 'external_id')
        ordering = ["sort_order", "id"]
        verbose_name = "设备控制节点"
        verbose_name_plural = "设备控制节点"

    def __str__(self):
        return f"{self.device.name} / {self.label}"


class DeviceAnomaly(models.Model):
    """
    设备异常事件记录，由后台 MonitorService 根据策略扫描生成。
    """
    class SeverityChoices(models.TextChoices):
        HIGH = "high", "高"
        MEDIUM = "medium", "中"
        LOW = "low", "低"

    # 账户关联
    account = models.ForeignKey(
        'accounts.Account',
        on_delete=models.CASCADE,
        related_name='device_anomalies',
        null=True,
        blank=True,
        verbose_name="所属账户"
    )
    external_id = models.CharField(max_length=128, verbose_name="外部异常 ID")
    room = models.ForeignKey(
        DeviceRoom,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="anomalies",
        verbose_name="关联房间"
    )
    device = models.ForeignKey(
        DeviceSnapshot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="anomalies",
        verbose_name="关联设备"
    )
    severity = models.CharField(
        max_length=16,
        choices=SeverityChoices.choices,
        default=SeverityChoices.LOW,
        verbose_name="严重程度"
    )
    title = models.CharField(max_length=255, verbose_name="异常标题")
    body = models.TextField(blank=True, verbose_name="详细描述")
    recommendation = models.TextField(blank=True, verbose_name="处理建议")
    is_active = models.BooleanField(default=True, verbose_name="是否处于激活态")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="排序权重")
    detected_at = models.DateTimeField(auto_now_add=True, verbose_name="检测到的时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "devices_anomaly"
        unique_together = ('account', 'external_id')
        ordering = ["sort_order", "-updated_at", "id"]
        verbose_name = "设备异常"
        verbose_name_plural = "设备异常"

    def __str__(self):
        return self.title


class DeviceAutomationRule(models.Model):
    """
    设备自动化规则/策略矩阵，规定了不同场景模式下的行为准则。
    """
    class DecisionChoices(models.TextChoices):
        ASK = "ask", "需确认"
        ALWAYS = "always", "自动执行"
        NEVER = "never", "从不执行"

    # 账户关联
    account = models.ForeignKey(
        'accounts.Account',
        on_delete=models.CASCADE,
        related_name='device_automation_rules',
        null=True,
        blank=True,
        verbose_name="所属账户"
    )
    external_id = models.CharField(max_length=128, verbose_name="外部规则 ID")
    room = models.ForeignKey(
        DeviceRoom,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rules",
        verbose_name="关联房间"
    )
    device = models.ForeignKey(
        DeviceSnapshot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rules",
        verbose_name="关联设备"
    )
    mode_key = models.CharField(max_length=32, verbose_name="模式标识", help_text="如 'away'")
    mode_label = models.CharField(max_length=64, verbose_name="模式显示名称", help_text="如 '离家'")
    target = models.CharField(max_length=255, verbose_name="策略目标字段", help_text="如 '客厅灯 / 开关'")
    condition = models.TextField(blank=True, verbose_name="生效条件描述")
    decision = models.CharField(
        max_length=16,
        choices=DecisionChoices.choices,
        default=DecisionChoices.ASK,
        verbose_name="执行决策方式"
    )
    rationale = models.TextField(blank=True, verbose_name="决策依据建议")
    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="排序权重")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "devices_automation_rule"
        unique_together = ('account', 'external_id')
        ordering = ["sort_order", "id"]
        verbose_name = "设备自动化规则"
        verbose_name_plural = "设备自动化规则"

    def __str__(self):
        return f"{self.mode_label}: {self.target}"
