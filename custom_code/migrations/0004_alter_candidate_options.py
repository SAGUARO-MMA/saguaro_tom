# Generated by Django 4.0.5 on 2022-06-09 19:28

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('custom_code', '0003_candidate'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='candidate',
            options={'ordering': ['-obsdate', '-candidatenumber']},
        ),
    ]
