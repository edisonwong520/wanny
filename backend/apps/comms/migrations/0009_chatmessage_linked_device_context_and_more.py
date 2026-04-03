from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("comms", "0008_learnedkeyword"),
    ]

    operations = [
        migrations.AddField(
            model_name="deviceoperationcontext",
            name="platform_user_id",
            field=models.CharField(blank=True, db_index=True, max_length=255, verbose_name="发起人标识"),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="linked_device_context",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="linked_chat_messages",
                to="comms.deviceoperationcontext",
                verbose_name="关联设备上下文",
            ),
        ),
    ]
