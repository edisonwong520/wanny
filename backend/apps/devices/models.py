from django.db import models


class DeviceDashboardState(models.Model):
    key = models.CharField(max_length=32, unique=True, default="default")
    source = models.CharField(max_length=32, default="demo")
    last_trigger = models.CharField(max_length=32, default="bootstrap")
    requested_trigger = models.CharField(max_length=32, blank=True, default="")
    refresh_requested_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    refreshed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "devices_dashboard_state"
        verbose_name = "Device Dashboard State"
        verbose_name_plural = "Device Dashboard States"

    def __str__(self):
        return f"{self.key} ({self.source})"


class DeviceRoom(models.Model):
    slug = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=64)
    climate = models.CharField(max_length=128, blank=True)
    summary = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "devices_room"
        ordering = ["sort_order", "id"]
        verbose_name = "Device Room"
        verbose_name_plural = "Device Rooms"

    def __str__(self):
        return self.name


class DeviceSnapshot(models.Model):
    class StatusChoices(models.TextChoices):
        ONLINE = "online", "Online"
        ATTENTION = "attention", "Attention"
        OFFLINE = "offline", "Offline"

    external_id = models.CharField(max_length=128, unique=True)
    room = models.ForeignKey(
        DeviceRoom,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="devices",
    )
    name = models.CharField(max_length=128)
    category = models.CharField(max_length=64)
    status = models.CharField(max_length=16, choices=StatusChoices.choices, default=StatusChoices.ONLINE)
    telemetry = models.CharField(max_length=255, blank=True)
    note = models.TextField(blank=True)
    capabilities = models.JSONField(default=list, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    source_payload = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "devices_snapshot"
        ordering = ["sort_order", "id"]
        verbose_name = "Device Snapshot"
        verbose_name_plural = "Device Snapshots"

    def __str__(self):
        return self.name


class DeviceAnomaly(models.Model):
    class SeverityChoices(models.TextChoices):
        HIGH = "high", "High"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Low"

    external_id = models.CharField(max_length=128, unique=True)
    room = models.ForeignKey(
        DeviceRoom,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="anomalies",
    )
    device = models.ForeignKey(
        DeviceSnapshot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="anomalies",
    )
    severity = models.CharField(max_length=16, choices=SeverityChoices.choices, default=SeverityChoices.LOW)
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    recommendation = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    detected_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "devices_anomaly"
        ordering = ["sort_order", "-updated_at", "id"]
        verbose_name = "Device Anomaly"
        verbose_name_plural = "Device Anomalies"

    def __str__(self):
        return self.title


class DeviceAutomationRule(models.Model):
    class DecisionChoices(models.TextChoices):
        ASK = "ask", "Ask"
        ALWAYS = "always", "Always"
        NEVER = "never", "Never"

    external_id = models.CharField(max_length=128, unique=True)
    room = models.ForeignKey(
        DeviceRoom,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rules",
    )
    device = models.ForeignKey(
        DeviceSnapshot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rules",
    )
    mode_key = models.CharField(max_length=32)
    mode_label = models.CharField(max_length=64)
    target = models.CharField(max_length=255)
    condition = models.TextField(blank=True)
    decision = models.CharField(max_length=16, choices=DecisionChoices.choices, default=DecisionChoices.ASK)
    rationale = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "devices_automation_rule"
        ordering = ["sort_order", "id"]
        verbose_name = "Device Automation Rule"
        verbose_name_plural = "Device Automation Rules"

    def __str__(self):
        return f"{self.mode_label}: {self.target}"
