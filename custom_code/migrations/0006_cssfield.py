# Generated by Django 4.1 on 2023-05-04 20:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("custom_code", "0005_candidate_mlscore_bogus_candidate_mlscore_real"),
    ]

    operations = [
        migrations.CreateModel(
            name="CSSField",
            fields=[
                (
                    "name",
                    models.CharField(max_length=6, primary_key=True, serialize=False),
                ),
                ("ra", models.FloatField()),
                ("dec", models.FloatField()),
                ("ecliptic_lng", models.FloatField()),
                ("ecliptic_lat", models.FloatField()),
                ("galactic_lng", models.FloatField()),
                ("galactic_lat", models.FloatField()),
                ("healpix", models.BigIntegerField()),
            ],
        ),
    ]

# After running this migration, populate the table using the following code:
# from astropy.table import Table
# from astropy.coordinates import SkyCoord
# from healpix_alchemy.constants import HPX
# from custom_code.models import CSSField
# t = Table.read('fieldlist.G96.txt', format='ascii',
#                names=['name', 'ra0', 'dec0', 'ecliptic_lng', 'ecliptic_lat', 'galactic_lng', 'galactic_lat'])
# sc = SkyCoord(t['ra0'], t['dec0'], unit=('hourangle', 'deg'))
# t['ra'] = sc.ra.deg
# t['dec'] = sc.dec.deg
# t['healpix'] = HPX.skycoord_to_healpix(sc)
# t.remove_columns(['ra0', 'dec0'])
# for row in t:
#     field = CSSField.objects.create(**row)
#     field.save()