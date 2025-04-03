# Generated by Django 4.2.16 on 2025-03-11 21:01

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tom_targets', '0021_rename_target_basetarget_alter_basetarget_options'),
        ('custom_code', '0025_delete_profile'),
    ]

    operations = [
        migrations.AlterField(
            model_name='candidate',
            name='target',
            field=models.ForeignKey(db_column='targetid', null=True, on_delete=django.db.models.deletion.SET_NULL, to='tom_targets.basetarget'),
        ),
    ]
