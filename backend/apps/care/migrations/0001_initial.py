from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("accounts", "0003_alter_account_name"),
        ("devices", "0007_expand_device_control_source_types_mbapi2020"),
        ("comms", "0007_mission_control_id_mission_control_key_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="InspectionRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("rule_type", models.CharField(choices=[("maintenance", "保养"), ("health", "健康"), ("custom", "自定义")], max_length=24, verbose_name="规则类型")),
                ("device_category", models.CharField(blank=True, max_length=64, verbose_name="设备分类")),
                ("name", models.CharField(max_length=128, verbose_name="规则名称")),
                ("description", models.TextField(blank=True, verbose_name="规则说明")),
                ("check_frequency", models.CharField(default="hourly", max_length=64, verbose_name="检查频率")),
                ("condition_spec", models.JSONField(blank=True, default=dict, verbose_name="条件规格")),
                ("action_spec", models.JSONField(blank=True, default=dict, verbose_name="建议动作")),
                ("suggestion_template", models.TextField(blank=True, verbose_name="建议模板")),
                ("priority", models.PositiveSmallIntegerField(default=5, verbose_name="基础优先级")),
                ("cooldown_hours", models.PositiveIntegerField(default=24, verbose_name="冷却小时数")),
                ("is_system_default", models.BooleanField(default=False, verbose_name="是否系统规则")),
                ("is_active", models.BooleanField(default=True, verbose_name="是否启用")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                ("account", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="inspection_rules", to="accounts.account", verbose_name="所属账户")),
            ],
            options={"db_table": "care_inspection_rule", "ordering": ["account_id", "-is_system_default", "name", "id"]},
        ),
        migrations.CreateModel(
            name="ExternalDataSource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_type", models.CharField(choices=[("weather_api", "天气 API"), ("ha_entity", "HA 实体"), ("other", "其他")], max_length=32, verbose_name="数据源类型")),
                ("name", models.CharField(max_length=128, verbose_name="数据源名称")),
                ("config", models.JSONField(blank=True, default=dict, verbose_name="配置")),
                ("fetch_frequency", models.CharField(default="30m", max_length=64, verbose_name="获取频率")),
                ("last_fetch_at", models.DateTimeField(blank=True, null=True, verbose_name="上次获取时间")),
                ("last_data", models.JSONField(blank=True, default=dict, verbose_name="最新数据")),
                ("is_active", models.BooleanField(default=True, verbose_name="是否启用")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="external_data_sources", to="accounts.account", verbose_name="所属账户")),
            ],
            options={"db_table": "care_external_data_source", "ordering": ["account_id", "name", "id"]},
        ),
        migrations.CreateModel(
            name="CareSuggestion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("suggestion_type", models.CharField(choices=[("inspection", "主动巡检"), ("care", "人文关怀")], max_length=24, verbose_name="建议类型")),
                ("title", models.CharField(max_length=255, verbose_name="标题")),
                ("body", models.TextField(verbose_name="详情")),
                ("action_spec", models.JSONField(blank=True, default=dict, verbose_name="动作规格")),
                ("priority", models.FloatField(default=0.0, verbose_name="优先级")),
                ("status", models.CharField(choices=[("pending", "待处理"), ("approved", "已采纳"), ("rejected", "已拒绝"), ("ignored", "已忽略"), ("executed", "已执行"), ("failed", "执行失败")], default="pending", max_length=24, verbose_name="状态")),
                ("dedupe_key", models.CharField(db_index=True, max_length=255, verbose_name="去重键")),
                ("aggregated_count", models.PositiveIntegerField(default=1, verbose_name="聚合数量")),
                ("source_event", models.JSONField(blank=True, default=dict, verbose_name="来源事件")),
                ("user_feedback", models.JSONField(blank=True, default=dict, verbose_name="用户反馈")),
                ("feedback_collected_at", models.DateTimeField(blank=True, null=True, verbose_name="反馈时间")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="care_suggestions", to="accounts.account", verbose_name="所属账户")),
                ("control_target", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="care_suggestions", to="devices.devicecontrol", verbose_name="执行控制目标")),
                ("device", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="care_suggestions", to="devices.devicesnapshot", verbose_name="关联设备")),
                ("mission", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="care_suggestions", to="comms.mission", verbose_name="关联任务")),
                ("source_rule", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="suggestions", to="care.inspectionrule", verbose_name="来源规则")),
            ],
            options={"db_table": "care_suggestion", "ordering": ["-priority", "-created_at", "-id"]},
        ),
    ]
