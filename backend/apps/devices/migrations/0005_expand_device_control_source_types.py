from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("devices", "0004_devicecontrol"),
    ]

    operations = [
        migrations.AlterField(
            model_name="devicecontrol",
            name="source_type",
            field=models.CharField(
                choices=[
                    ("ha_entity", "Home Assistant 实体"),
                    ("mijia_property", "米家属性"),
                    ("mijia_action", "米家动作"),
                    ("midea_cloud_property", "美的云属性"),
                    ("midea_cloud_action", "美的云动作"),
                ],
                max_length=32,
                verbose_name="来源类型",
            ),
        ),
    ]
