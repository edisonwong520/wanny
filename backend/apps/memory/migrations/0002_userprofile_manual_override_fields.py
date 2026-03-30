from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("memory", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="source",
            field=models.CharField(
                choices=[("review", "定时复盘"), ("manual", "用户手动修改")],
                default="review",
                help_text="当前画像值的来源：定时复盘或用户手动修改",
                max_length=20,
                verbose_name="Source",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="is_user_edited",
            field=models.BooleanField(
                default=False,
                help_text="是否由用户手动修改；若为 True，后续复盘应优先保留该值",
                verbose_name="Is User Edited",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="last_review_value",
            field=models.TextField(
                blank=True,
                default="",
                help_text="当用户手动修改后，最近一次定时复盘建议的值会记录在这里，供后续融合或审计",
                verbose_name="Last Review Suggested Value",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="last_review_confidence",
            field=models.FloatField(
                blank=True,
                help_text="最近一次复盘建议的置信度",
                null=True,
                verbose_name="Last Review Confidence",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="last_review_at",
            field=models.DateTimeField(
                blank=True,
                help_text="最近一次复盘处理该画像的时间",
                null=True,
                verbose_name="Last Review At",
            ),
        ),
    ]
