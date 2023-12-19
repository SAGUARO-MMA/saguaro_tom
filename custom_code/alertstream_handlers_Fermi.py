''' This class defines a message handler for a tom_alertstreams connection to Fermi GRB events

'''
import logging
import os
import traceback
import requests
from django.conf import settings
import time

from tom_nonlocalizedevents.alertstream_handlers.gcn_event_handler import handle_message
from tom_nonlocalizedevents.models import NonLocalizedEvent, EventSequence
from tom_nonlocalizedevents.healpix_utils import create_localization_for_skymap

logger = logging.getLogger(__name__)


EXPECTED_FIELDS = [
    'trigger_num',
    'notice_type',
    'pos_map_url'
]

def get_sequence_number(superevent_id: str) -> int:
    """ This returns the sequence number of the next sequence for a superevent_id. This is a hack to get
        around the fact that IGWN GWAlerts no longer tell you the sequence number within them.
    """
    try:
        nle = NonLocalizedEvent.objects.get(event_id=superevent_id)
        return nle.sequences.count() + 1
    except NonLocalizedEvent.DoesNotExist:
        return 1  # The nonlocalizedevent doesnt exist in our system yet, so this must be the first sequence

def extract_all_fields(message):
    parsed_fields = {}
    for line in message.splitlines():
        entry = line.split(':', maxsplit=1)
        if len(entry) > 1:
            if entry[0].strip() == 'COMMENTS' and 'comments' in parsed_fields:
                parsed_fields['comments'] += entry[1].lstrip()
            else:
                parsed_fields[entry[0].strip().lower()] = entry[1].strip()
    return parsed_fields


def get_moc_url_from_skymap_fits_url(pos_map_url):
    base, filename = os.path.split(pos_map_url)
    # Repair broken skymap filenames given in gcn mock alerts right now
    if filename.endswith('.fit'):
        filename = filename + 's'
    # Replace the non-MOC skymap url provided with the MOC version, but keep the ,# on the end
   # filename = filename.replace('LALInference.fits.gz', 'LALInference.multiorder.fits')
   # filename = filename.replace('bayestar.fits.gz', 'bayestar.multiorder.fits')
    return os.path.join(base, filename)


def handle_message_Fermi(message):
    # It receives a bytestring message or a Kafka message in the LIGO GW format
    # fields must be extracted from the message text and stored into in the model
    # It returns the nonlocalizedevent and event sequence ingested or None, None.


    # ingest NonLocalizedEvent into the TOM database

    if not isinstance(message, bytes):
        bytes_message = message.value()
    else:
        bytes_message = message
    logger.warning(f"Processing message: {bytes_message.decode('utf-8')}")
    fields = extract_all_fields(bytes_message.decode('utf-8'))
    if not all(field in fields.keys() for field in EXPECTED_FIELDS):
        logger.warning(f"Incoming Fermi GRB message did not have the expected fields, ignoring it: {fields.keys()}")
        return
     # ingest NonLocalizedEvent into the TOM database
 #   nle, seq = handle_message(message, metadata)

   # if fields and fields['trigger_num'].startswith('M') and not settings.SAVE_TEST_ALERTS:
   #     return

    if fields:
        nonlocalizedevent, nle_created = NonLocalizedEvent.objects.get_or_create(
            event_id=fields['trigger_num'],
            event_type=NonLocalizedEvent.NonLocalizedEventType.GAMMA_RAY_BURST,
        )
        if nle_created:
            logger.info(f"Ingested a new Fermi GRB event with id {fields['trigger_num']} from alertstream")
        # Next attempt to ingest and build the localization of the event
       
        skymap_url = get_moc_url_from_skymap_fits_url(fields['pos_map_url'])
        counter =0
        while counter<5:
            try:
                skymap_resp = requests.get(skymap_url)
                skymap_resp.raise_for_status()
                localization = create_localization_for_skymap(
                    nonlocalizedevent=nonlocalizedevent,
                    skymap_bytes=skymap_resp.content,
                    skymap_url=skymap_url
                )
                break
            except Exception as e:
                localization = None
                logger.error(
                    f"Failed to retrieve and process localization from skymap file at {skymap_url}. Exception: {e}"
                )
                logger.error(traceback.format_exc())
                time.sleep(30)
                counter +=1
        # Now ingest the sequence for that event
        sequence_number = 1 # get_sequence_number(alert['superevent_id'])
        event_sequence, es_created = EventSequence.objects.update_or_create(
            nonlocalizedevent=nonlocalizedevent,
            localization=localization,
            sequence_id=sequence_number,
            #_id=fields['notice_type'],
            defaults={
                'event_subtype': fields['notice_type'],
                'details': fields,
                'ingestor_source': 'gcn'
            }
        )
        if es_created and localization is None:
            warning_msg = (f'{"Creating" if es_created else "Updating"} EventSequence without EventLocalization:'
                           f'{event_sequence} for NonLocalizedEvent: {nonlocalizedevent}')
            logger.warning(warning_msg)

        return nonlocalizedevent, event_sequence
    return None, None



    
