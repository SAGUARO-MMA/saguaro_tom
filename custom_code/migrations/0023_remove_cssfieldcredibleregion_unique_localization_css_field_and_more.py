# Generated by Django 4.2 on 2023-08-22 21:35

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        (
            "tom_nonlocalizedevents",
            "0017_alter_eventsequence_external_coincidence_and_more",
        ),
        ("tom_surveys", "0004_alter_surveyobservationrecord_options"),
        ("custom_code", "0022_remove_candidate_filename"),
    ]

    operations = [
        migrations.RenameModel("CSSFieldCredibleRegion", "SurveyFieldCredibleRegion"),
        migrations.RenameField("SurveyFieldCredibleRegion", "first_observable", "scheduled_start"),
        migrations.RenameField("SurveyFieldCredibleRegion", "css_field", "survey_field"),
        migrations.RemoveConstraint(
            model_name="SurveyFieldCredibleRegion",
            name="unique_localization_css_field",
        ),
        migrations.AddConstraint(
            model_name="SurveyFieldCredibleRegion",
            constraint=models.UniqueConstraint(
                fields=("localization", "survey_field"),
                name="unique_localization_survey_field",
            ),
        ),
    ]