# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2019-03-01 05:24
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0006_userprofile_device_token'),
    ]

    operations = [
        migrations.CreateModel(
            name='BotCommand',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('command_name', models.CharField(choices=[('food', 'FOOD_DROP_AREAS'), ('safe', 'SAFE_LOCATIONS'), ('contact', 'EMERGENCY_CONTACTS')], max_length=10, unique=True)),
                ('command_response', models.TextField(default='')),
            ],
        ),
    ]
