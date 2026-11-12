import django_tables2 as tables
from django.utils import timezone

from tom_targets.tables import TargetTable as OldTargetTable


class TargetTable(OldTargetTable):
    """
    Upstream TargetTable plus distance, photometry/spectra counts, and the latest detection.
    The counts and latest detection come from annotations added in custom_code.views.TargetListView.get_queryset.
    """
    distance = tables.Column('Distance (Mpc)')
    n_photometry = tables.Column('Phot. Points')
    n_spectra = tables.Column('Spectra')
    # sorts by detection time; shows the magnitude and how long ago it was
    latest_det_time = tables.Column('Last Mag (Days Ago)')

    def render_distance(self, value):
        return f'{value:.1f}'

    def render_latest_det_time(self, value, record):
        days_ago = (timezone.now() - value).total_seconds() / 86400.
        return f'{record.latest_det_mag:.2f} ({days_ago:.1f})'

    class Meta(OldTargetTable.Meta):
        fields = ['selection', 'name', 'ra', 'dec', 'distance', 'n_photometry', 'n_spectra', 'latest_det_time']
        exclude = ['type']
