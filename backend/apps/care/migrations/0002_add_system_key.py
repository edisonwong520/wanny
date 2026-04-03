from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("care", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="inspectionrule",
            name="system_key",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64, verbose_name="系统规则键"),
            preserve_default=False,
        ),
    ]
