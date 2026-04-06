from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("devices", "0007_expand_device_control_source_types_mbapi2020"),
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
                    ("midea_cloud_property", "美的属性"),
                    ("midea_cloud_action", "美的动作"),
                    ("mbapi2020_property", "奔驰属性"),
                    ("mbapi2020_action", "奔驰动作"),
                    ("hisense_ha_property", "海信属性"),
                    ("hisense_ha_action", "海信动作"),
                ],
                max_length=32,
                verbose_name="来源类型",
            ),
        ),
    ]
