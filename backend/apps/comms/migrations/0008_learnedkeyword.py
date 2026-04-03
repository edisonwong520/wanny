from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
        ("comms", "0007_mission_control_id_mission_control_key_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="LearnedKeyword",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("keyword", models.CharField(max_length=64, verbose_name="原始关键词")),
                ("normalized_keyword", models.CharField(db_index=True, max_length=64, verbose_name="归一化关键词")),
                ("canonical", models.CharField(blank=True, max_length=64, verbose_name="标准映射")),
                ("canonical_payload", models.JSONField(blank=True, default=dict, verbose_name="结构化映射")),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("device", "设备"),
                            ("room", "房间"),
                            ("control", "控制项"),
                            ("action", "动作"),
                            ("colloquial", "口语化"),
                        ],
                        max_length=24,
                        verbose_name="关键词分类",
                    ),
                ),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("history", "历史对话"),
                            ("device", "设备数据库"),
                            ("user", "用户自定义"),
                            ("system", "系统预置"),
                        ],
                        max_length=24,
                        verbose_name="关键词来源",
                    ),
                ),
                ("confidence", models.FloatField(default=0.5, verbose_name="置信度")),
                ("usage_count", models.IntegerField(default=1, verbose_name="使用次数")),
                ("last_used_at", models.DateTimeField(blank=True, null=True, verbose_name="最后使用时间")),
                ("learned_at", models.DateTimeField(auto_now_add=True, verbose_name="学习时间")),
                ("is_active", models.BooleanField(default=True, verbose_name="是否启用")),
                (
                    "account",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="learned_keywords",
                        to="accounts.account",
                        verbose_name="所属账户",
                    ),
                ),
            ],
            options={
                "verbose_name": "学习关键词",
                "verbose_name_plural": "学习关键词",
                "db_table": "comms_learned_keyword",
                "ordering": ["account_id", "category", "-confidence", "-usage_count", "normalized_keyword"],
            },
        ),
        migrations.AddConstraint(
            model_name="learnedkeyword",
            constraint=models.UniqueConstraint(
                condition=Q(account__isnull=False),
                fields=("account", "normalized_keyword", "category"),
                name="uniq_learned_keyword_account",
            ),
        ),
        migrations.AddConstraint(
            model_name="learnedkeyword",
            constraint=models.UniqueConstraint(
                condition=Q(account__isnull=True),
                fields=("normalized_keyword", "category"),
                name="uniq_learned_keyword_global",
            ),
        ),
    ]
