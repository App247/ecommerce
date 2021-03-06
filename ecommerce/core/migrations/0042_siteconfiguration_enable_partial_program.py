# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-08-04 14:50
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0041_remove_siteconfiguration__allowed_segment_events'),
    ]

    operations = [
        migrations.AddField(
            model_name='siteconfiguration',
            name='enable_partial_program',
            field=models.BooleanField(default=False, help_text='Enable the application of program offers to remaining unenrolled or unverified courses', verbose_name='Enable Partial Program Offer'),
        ),
    ]
