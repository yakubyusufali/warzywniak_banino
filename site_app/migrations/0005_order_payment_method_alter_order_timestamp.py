# Generated by Django 5.1.4 on 2024-12-14 08:52

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('site_app', '0004_alter_order_sum'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='payment_method',
            field=models.CharField(default='cash', max_length=7),
        ),
        migrations.AlterField(
            model_name='order',
            name='timestamp',
            field=models.DateTimeField(default=datetime.datetime(2024, 12, 14, 8, 52, 55, 114612, tzinfo=datetime.timezone.utc)),
        ),
    ]
