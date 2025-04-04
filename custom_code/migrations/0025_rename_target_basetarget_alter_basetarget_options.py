from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tom_observations', '0012_auto_20210205_1819'),
        ('tom_dataproducts', '0012_alter_reduceddatum_data_product_and_more'),
        ('tom_targets', '0020_alter_targetname_created_alter_targetname_modified'),
        ('tom_nonlocalizedevents', '0017_alter_eventsequence_external_coincidence_and_more'),
        ('custom_code', '0024_remove_surveyfieldcredibleregion_treasuremap_id_and_more'),
    ]

    replaces = [('tom_targets', '0021_rename_target_basetarget_alter_basetarget_options')]

    operations = [
        migrations.RenameModel(
            old_name='Target',
            new_name='BaseTarget',
        ),
        migrations.AlterModelOptions(
            name='basetarget',
            options={'permissions': (('view_target', 'View Target'), ('add_target', 'Add Target'), ('change_target', 'Change Target'), ('delete_target', 'Delete Target')), 'verbose_name': 'target'},
        ),
    ]
