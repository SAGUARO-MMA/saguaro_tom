import django_tables2 as tables

from tom_targets.tables import TargetTable as OldTargetTable


class TargetTable(OldTargetTable):
    """
    Upstream TargetTable plus distance and photometry/spectra counts.
    The counts come from annotations added in custom_code.views.TargetListView.get_queryset.
    """
    distance = tables.Column('Distance (Mpc)')
    n_photometry = tables.Column('Phot. Points')
    n_spectra = tables.Column('Spectra')

    def render_distance(self, value):
        return f'{value:.1f}'

    class Meta(OldTargetTable.Meta):
        fields = ['selection', 'name', 'ra', 'dec', 'distance', 'n_photometry', 'n_spectra']
        exclude = ['type']
