from django.core.management.base import BaseCommand
from tom_observations.facility import get_service_class
from tom_observations.models import ObservationRecord


def update_status_and_download_data(record):
    """Updates status and downloads selected data for pending observations"""
    record.update_status()
    facility = get_service_class(record.facility)()
    products = facility.data_products(record.observation_id)
    for product in products:
        if (product['filename'].endswith('.tar.gz')
                or product['filename'].endswith('.e91-1d.fits.fz')
                or product['filename'].endswith('.fits.fz')
                or product['filename'] == 'obj_abs_1D.tar'):
            facility.save_data_products(record, product['id'])


class Command(BaseCommand):
    help = 'Updates status and downloads selected data for pending observations'

    def handle(self, *args, **options):
        observation_records = ObservationRecord.objects.filter(status='PENDING')
        for record in observation_records:
            update_status_and_download_data(record)
