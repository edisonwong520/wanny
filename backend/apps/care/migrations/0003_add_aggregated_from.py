from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("care", "0002_add_system_key"),
    ]

    operations = [
        migrations.AddField(
            model_name="caresuggestion",
            name="aggregated_from",
            field=models.JSONField(blank=True, default=list, verbose_name="聚合来源"),
        ),
    ]
