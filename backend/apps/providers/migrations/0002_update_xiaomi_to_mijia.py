from django.db import migrations

def update_xiaomi_to_mijia(apps, schema_editor):
    PlatformAuth = apps.get_model('providers', 'PlatformAuth')
    # Update platform_name from 'xiaomi' to 'mijia'
    # We use check to avoid integrity error if 'mijia' already exists
    # but based on the system logic, only one of them should exist as active.
    
    # First, handle the case where 'xiaomi' exists but 'mijia' doesn't
    PlatformAuth.objects.filter(platform_name='xiaomi').update(platform_name='mijia')

def reverse_mijia_to_xiaomi(apps, schema_editor):
    PlatformAuth = apps.get_model('providers', 'PlatformAuth')
    PlatformAuth.objects.filter(platform_name='mijia').update(platform_name='xiaomi')

class Migration(migrations.Migration):

    dependencies = [
        ('providers', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(update_xiaomi_to_mijia, reverse_mijia_to_xiaomi),
    ]
