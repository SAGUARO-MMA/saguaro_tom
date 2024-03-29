# Generated by Django 4.2 on 2023-08-10 20:50

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("tom_surveys", "0002_surveyfield_and_more"),
    ]

    # these are required for the previous migration (0002) to fully work
    operations = [
        migrations.RunSQL(
            [
                'ALTER TABLE tom_surveys_surveyfield_adjacent RENAME COLUMN from_cssfield_id to from_surveyfield_id',
                'ALTER TABLE tom_surveys_surveyfield_adjacent RENAME COLUMN to_cssfield_id to to_surveyfield_id',
                'ALTER TABLE custom_code_cssfield_adjacent_id_seq RENAME TO tom_surveys_surveyfield_adjacent_id_seq',
            ]
        )
    ]
