from django.core.management.base import BaseCommand
from tom_observations.models import ObservationRecord
from tom_observations.facilities import lco, ocs
from tom_targets.models import get_target_model_class
from tom_targets.utils import cone_search_filter
from datetime import datetime, timedelta
from urllib.parse import urlencode, urljoin
import logging

logger = logging.getLogger(__name__)
facility = lco.LCOFacility()
Target = get_target_model_class()


class Command(BaseCommand):

    help = 'Records all available LCO observation requests in our TOM'

    def add_arguments(self, parser):
        parser.add_argument('--created-after', help='Sync observation requests created after this date (default 1 hour ago)')
        parser.add_argument('--created-before', help='Sync observation requests created before this date')

    def handle(self, *args, **options):
        query_options = {}
        if options['created_after']:
            query_options['created_after'] = options['created_after']
        else:
            query_options['created_after'] = (datetime.now() - timedelta(hours=1.)).strftime('%Y-%m-%dT%H:%M:00Z')
        if options['created_before']:
            query_options['created_before'] = options['created_before']
        query_params = urlencode(query_options)
        response = ocs.make_request(
            'GET',
            urljoin(facility.facility_settings.get_setting('portal_url'), f'/api/requestgroups/?{query_params}'),
            headers=facility._portal_headers()
        )
        response.raise_for_status()
        for result in response.json()['results']:
            for request in result['requests']:
                obs = ObservationRecord.objects.filter(facility=facility.name, observation_id=request['id']).first()
                if obs:
                    logger.info(f'Observation record {obs.observation_id} for target {obs.target.name} already exists')
                else:
                    target = request['configurations'][0]['target']
                    target_matches = cone_search_filter(Target.objects, target['ra'], target['dec'], 2. / 3600.)

                    obs = ObservationRecord.objects.create(
                        target=target_matches.first(),
                        facility=facility.name,
                        parameters={},
                        status=request['state'],
                        observation_id=request['id'],
                        created=result['created'],
                        modified=request['modified'],
                    )
                    logger.info(f'Created new observation record {obs.observation_id} for target {obs.target.name}')

                    obs.update_status()
                    products = facility.data_products(obs.observation_id)
                    for product in products:
                        if product['filename'].endswith('.tar.gz'):
                            facility.save_data_products(obs, product['id'])
