# Generated by Django 4.2 on 2023-08-10 20:12

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("tom_surveys", "0002_surveyfield_and_more"),
        ("custom_code", "0019_cssfieldcredibleregion_treasuremap_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="cssfieldcredibleregion",
            name="observation_record",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="tom_surveys.surveyobservationrecord",
            ),
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="candidate",
                    name="field",
                    field=models.ForeignKey(
                        db_column="field",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="tom_surveys.surveyfield",
                    ),
                ),
            ],
            database_operations=[],  # reusing existing table
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="cssfieldcredibleregion",
                    name="css_field",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="css_field_credible_regions",
                        to="tom_surveys.surveyfield",
                    ),
                ),
            ],
            database_operations=[],  # reusing existing table
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="cssfieldcredibleregion",
                    name="css_field",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="css_field_credible_regions",
                        to="tom_surveys.surveyfield",
                    ),
                ),
            ],
            database_operations=[],  # reusing existing table
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(
                    name="CSSField",
                ),
            ],
            database_operations=[
                migrations.AlterModelTable(
                    name="CSSField",
                    table="tom_surveys_surveyfield",
                ),
            ],
        ),
    ]
