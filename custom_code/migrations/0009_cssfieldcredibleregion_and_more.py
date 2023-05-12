# Generated by Django 4.1 on 2023-05-05 21:23

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        (
            "tom_nonlocalizedevents",
            "0017_alter_eventsequence_external_coincidence_and_more",
        ),
        ("custom_code", "0008_alter_candidate_field"),
    ]

    operations = [
        migrations.CreateModel(
            name="CSSFieldCredibleRegion",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "smallest_percent",
                    models.IntegerField(
                        default=100,
                        help_text="Smallest percent credible region this field falls into for this localization.",
                    ),
                ),
                (
                    "css_field",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="css_field_credible_regions",
                        to="custom_code.cssfield",
                    ),
                ),
                (
                    "localization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="css_field_credible_regions",
                        to="tom_nonlocalizedevents.eventlocalization",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="cssfieldcredibleregion",
            constraint=models.UniqueConstraint(
                fields=("localization", "css_field"),
                name="unique_localization_css_field",
            ),
        ),
    ]