from tom_nonlocalizedevents.models import NonLocalizedEvent, EventSequence, EventCandidate
from tom_nonlocalizedevents.alertstream_handlers.igwn_event_handler import handle_igwn_message
from django.contrib.auth.models import Group
from django.conf import settings
from email.mime.text import MIMEText
import requests
import smtplib
import logging
import json
from .templatetags.nonlocalizedevent_extras import format_inverse_far, format_distance, format_area, get_most_likely_class
from .healpix_utils import update_all_credible_region_percents_for_survey_fields, create_elliptical_localization
from .cssfield_selection import calculate_footprint_probabilities, rank_css_fields
from .models import CredibleRegionContour
from astropy.table import Table
from io import BytesIO
import astropy_healpix as ah
import numpy as np
import traceback
from tom_targets.models import Target

logger = logging.getLogger(__name__)

# for einstein probe
ALERT_TEXT_EP = """Einstein Probe trigger {{target.name}}
<{nle_link}|Localization>
<{target_link}|Target>
"""

# for icecube
ALERT_TEXT_IC = """IceCube trigger {{target.name}}
<{nle_link}|Localization>
<{target_link}|Target>
"""


ALERT_TEXT_INTRO = """{{most_likely_class}} {{seq.event_subtype}} v{{seq.sequence_id}}
{{nle.event_id}} ({{significance}})
{{time}}
1/FAR = {{inverse_far}}
"""

ALERT_TEXT_LOCALIZATION = """Distance = {{distance}}
50% Area = {{area_50}}
90% Area = {{area_90}}
"""

ALERT_TEXT_EXTERNAL_COINCIDENCE = """
Coincident with {{observatory}} {{search}}
GCN Notice {{gcn_notice_id}}
Δt = {{time_difference:.2f}} s
1/FAR (time) = {{inverse_far_time}}
1/FAR (time + pos.) = {{inverse_far_time_pos}}
Distance (comb.) = {{distance_external}}
50% Area (comb.) = {{area_50_external}}
90% Area (comb.) = {{area_90_external}}
"""

ALERT_TEXT_CLASSIFICATION = """Has NS = {{HasNS:.0%}}
Has Mass Gap = {{HasMassGap:.0%}}
Has Remnant = {{HasRemnant:.0%}}
BNS = {{BNS:.0%}}
NSBH = {{NSBH:.0%}}
BBH = {{BBH:.0%}}
Terrestrial = {{Terrestrial:.0%}}
"""

# links for Slack
ALERT_LINKS = ('<{nle_link}|{service}> <{{nle.hermes_url}}|Hermes> '
               '<{{nle.gracedb_url}}|GraceDB> <{{nle.treasuremap_url}}|Treasure Map>')

ALERT_TEXT_RETRACTION = "{{most_likely_class}} {{nle.event_id}} {{nle.state}}"

ALERT_TEXT_BURST = ALERT_TEXT_INTRO + """50% Area = {{seq.localization.area_50:.0f}} deg²
90% Area = {{seq.localization.area_90:.0f}} deg²
Duration = {{duration_ms:.0f}} ms
Frequency = {{central_frequency:.0f}} Hz
""" + ALERT_LINKS

ALERT_TEXT_SSM = ALERT_TEXT_INTRO + ALERT_TEXT_LOCALIZATION + """Has NS = {{HasNS:.0%}}
Has Mass Gap = {{HasMassGap:.0%}}
Has SSM = {{HasSSM:.0%}}
""" + ALERT_LINKS

ALERT_TEXT = [  # index = number of localizations available
    ALERT_TEXT_INTRO + ALERT_TEXT_CLASSIFICATION + ALERT_LINKS,
    ALERT_TEXT_INTRO + ALERT_TEXT_LOCALIZATION + ALERT_TEXT_CLASSIFICATION + ALERT_LINKS,
    ALERT_TEXT_INTRO + ALERT_TEXT_LOCALIZATION + ALERT_TEXT_CLASSIFICATION + ALERT_TEXT_EXTERNAL_COINCIDENCE +
    ALERT_LINKS,
]


def send_slack(body, format_kwargs, is_test_alert=False, is_significant=True, is_burst=False, has_ns=True,
               all_workspaces=True, at=None):
    if is_test_alert:
        channel = None
    elif not is_significant:
        channel = 0
    elif is_burst:
        channel = 1
    elif not has_ns:
        channel = 2
    else:
        channel = 3
    if at is not None:
        body = f'<!{at}>\n' + body
    headers = {'Content-Type': 'application/json'}
    for url_list, (nle_link, service), (target_link, _) in zip(settings.SLACK_URLS, settings.NLE_LINKS, settings.TARGET_LINKS):
        body_slack = body.format(nle_link=nle_link, service=service, target_link=target_link).format(**format_kwargs)
        logger.info(f'Sending GW alert: {body_slack}')
        if channel is None:
            break  # just print out test alerts for debugging
        json_data = json.dumps({'text': body_slack})
        requests.post(url_list[channel], data=json_data.encode('ascii'), headers=headers)
        if not all_workspaces:
            break


def send_email(subject, body, is_test_alert=False):
    """This doesn't currently work"""
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = settings.ALERT_EMAIL_FROM
    group = Group.objects.get(name='Test Email Alerts') if is_test_alert else Group.objects.get(name='Email Alerts')
    msg['To'] = ','.join([u.email.split(',')[0] for u in group.user_set.all()])
    if not msg['To']:
        logger.info(f'Email "{subject}" not sent. No one is subscribed.')
        return
    email_text = msg.as_string()

    try:
        server = smtplib.SMTP()
        server.connect()
        server.sendmail(msg['From'], msg['To'], email_text)
        server.close()
        logger.info(f'Email "{subject}" sent!')
    except Exception as e:
        logger.error(f'Email "{subject}" failed: {e}')


def calculate_credible_region(skymap, localization, probability=0.9):
    """store the credible region contour for skymap plotting"""
    # Sort the pixels of the sky map by descending probability density
    skymap.sort('PROBDENSITY', reverse=True)
    # Find the area of each pixel
    skymap['level'], skymap['ipix'] = ah.uniq_to_level_ipix(skymap['UNIQ'])
    pixel_area = ah.nside_to_pixel_area(ah.level_to_nside(skymap['level']))
    # Calculate the probability within each pixel: the pixel area times the probability density
    prob = pixel_area * skymap['PROBDENSITY']
    # Calculate the cumulative sum of the probability
    cumprob = np.cumsum(prob)
    # Find the pixel for which the probability sums to 0.9
    index_90 = cumprob.searchsorted(probability)
    # Find the pixels included in this sum
    skymap90 = skymap[:index_90].group_by('level')
    credible_region_90 = {str(group['level'][0]): [ipix.item() for ipix in group['ipix']] for group in skymap90.groups}
    if 'MOCORDER' in skymap.meta:
        credible_region_90.setdefault(str(skymap.meta['MOCORDER']), [])  # must include the highest order
    # Create the CredibleRegionContour object
    CredibleRegionContour(localization=localization, probability=probability, pixels=credible_region_90).save()
    logger.info('Calculated skymap contours')


def pick_slack_channel(seq):
    is_test_alert = seq.nonlocalizedevent.event_id.startswith('M')
    is_significant = seq.details['significant']
    is_burst = seq.details['group'] == 'Burst'
    has_ns = seq.details['properties'].get('HasNS', 0.) >= 0.01 \
             or seq.details['classification'].get('BNS', 0.) >= 0.01 \
             or seq.details['classification'].get('NSBH', 0.) >= 0.01
    return is_test_alert, is_significant, is_burst, has_ns


def prepare_and_send_alerts(nle, seq):
    localizations = []
    try:
        if seq is None:  # retraction
            seq = nle.sequences.last()
        else:
            if seq.localization is not None:
                localizations.append(seq.localization)
            if seq.external_coincidence is not None and seq.external_coincidence.localization is not None:
                localizations.append(seq.external_coincidence.localization)
        is_test_alert, is_significant, is_burst, has_ns = pick_slack_channel(seq)
        format_kwargs = {
            'nle': nle,
            'seq': seq,
            'most_likely_class': get_most_likely_class(seq.details),
            'inverse_far': format_inverse_far(seq.details['far']),
            'significance': 'significant' if is_significant else 'subthreshold',
        }
        format_kwargs.update(seq.details['properties'])
        format_kwargs.update(seq.details['classification'])
        format_kwargs.update(seq.details)
        if nle.state == 'RETRACTED':
            alert_text = ALERT_TEXT_RETRACTION
        elif is_burst:
            alert_text = ALERT_TEXT_BURST
            format_kwargs['duration_ms'] = seq.details['duration'] * 1000.
        else:
            if seq.details['search'] == 'SSM':
                alert_text = ALERT_TEXT_SSM
            else:
                alert_text = ALERT_TEXT[len(localizations)]
            if localizations:
                format_kwargs['distance'] = format_distance(localizations[0])
                format_kwargs['area_50'] = format_area(localizations[0].area_50)
                format_kwargs['area_90'] = format_area(localizations[0].area_90)
            if len(localizations) > 1:
                format_kwargs.update(seq.external_coincidence.details)
                format_kwargs['inverse_far_time'] = format_inverse_far(format_kwargs['time_coincidence_far'])
                format_kwargs['inverse_far_time_pos'] = format_inverse_far(format_kwargs['time_sky_position_coincidence_far'])
                format_kwargs['distance_external'] = format_distance(localizations[1])
                format_kwargs['area_50_external'] = format_area(localizations[1].area_50)
                format_kwargs['area_90_external'] = format_area(localizations[1].area_90)
    except Exception as e:
        logger.error(f'Could not parse GW alert: {e}')
        alert_text = f'Received a GW alert that could not be parsed. Check GraceDB: {nle.gracedb_url}'
        format_kwargs = {}
        is_test_alert = nle.event_id.startswith('M')
        is_significant = False
        is_burst = False
        has_ns = False
    if is_significant and not is_burst and has_ns:
        at = 'here' if nle.state == 'RETRACTED' else 'channel'
    else:
        at = None
    send_slack(alert_text, format_kwargs,
               is_test_alert=is_test_alert, is_significant=is_significant, is_burst=is_burst, has_ns=has_ns, at=at)
    return localizations


def handle_message_and_send_alerts(message, metadata):
    # get skymap bytes out for later
    skymaps = []
    try:
        alert = message.content[0]
        event = alert.get('event')
        if event is not None:
            skymaps.append(event.get('skymap'))
        external_coinc = alert.get('external_coinc')
        if external_coinc is not None:
            skymaps.append(external_coinc.get('combined_skymap'))
    except Exception as e:  # no matter what, do not crash the listener before ingesting the alert
        logger.error(f'Could not extract skymap from alert: {e}')

    # ingest NonLocalizedEvent into the TOM database
    nle, seq = handle_igwn_message(message, metadata)

    if nle is None:  # test event and SAVE_TEST_ALERTS = False
        logger.info('Test alert not saved')
        return

    localizations = prepare_and_send_alerts(nle, seq)

    for skymap_bytes, localization in zip(skymaps, localizations):
        if CredibleRegionContour.objects.filter(localization=localization).exists():
            logger.info(f'Localization {localization.id} already exists')
        else:
            update_all_credible_region_percents_for_survey_fields(localization)
            if skymap_bytes is not None:
                skymap = Table.read(BytesIO(skymap_bytes))
                calculate_credible_region(skymap, localization)
                calculate_footprint_probabilities(skymap, localization)
                rank_css_fields(localization.surveyfieldcredibleregions)

    logger.info(f'Finished processing alert for {nle.event_id}')


def handle_einstein_probe_alert(message, metadata):
    alert = message.content
    logger.warning(f"Handling Einstein Probe alert: {alert}")

    nonlocalizedevent, nle_created = NonLocalizedEvent.objects.get_or_create(
        event_id=alert['id'][0],
        event_type=NonLocalizedEvent.NonLocalizedEventType.UNKNOWN,
    )
    if nle_created:
        logger.info(f"Ingested a new x-ray event with id {nonlocalizedevent.event_id} from EP alert stream")

    # create the localization from ra, dec, radius
    try:
        localization, skymap = create_elliptical_localization(
            nonlocalizedevent=nonlocalizedevent,
            center=[alert.get('ra'), alert.get('dec')], radius=alert.get('ra_dec_error'),
        )
    except Exception as e:
        localization = None
        skymap = None
        logger.error(f'Could not create EventLocalization for event: {nonlocalizedevent.event_id}. Exception: {e}')
        logger.error(traceback.format_exc())

    logger.debug(f"Storing EP alert: {alert}")

    # Now ingest the sequence for that event
    details = {key: alert.get(key) for key in
               ['instrument', 'image_energy_range', 'net_count_rate', 'image_snr', 'additional_info']}
    details['time'] = alert.get('trigger_time')  # to match IGWN alerts
    event_sequence, es_created = EventSequence.objects.update_or_create(
        nonlocalizedevent=nonlocalizedevent,
        localization=localization,
        sequence_id=nonlocalizedevent.sequences.count() + 1,
        details=details,
    )
    if es_created and localization is None:
        warning_msg = (
            f'{"Creating" if es_created else "Updating"} EventSequence without EventLocalization:'
            f'{event_sequence} for NonLocalizedEvent: {nonlocalizedevent}'
        )
        logger.warning(warning_msg)

    if CredibleRegionContour.objects.filter(localization=localization).exists():
        logger.info(f'Localization {localization.id} already exists')
    else:
        update_all_credible_region_percents_for_survey_fields(localization)
        if skymap is not None:
            skymap['PROBDENSITY'].unit = '1 / sr'
            calculate_credible_region(skymap, localization)
            calculate_footprint_probabilities(skymap, localization)
            rank_css_fields(localization.surveyfieldcredibleregions)

    ep_ra = alert.get('ra')
    ep_dec = alert.get('dec')
    ep_name = alert['id'][0]
    t_ep = Target.objects.create(name=ep_name, type='SIDEREAL', ra=ep_ra, dec=ep_dec, permissions='PUBLIC')
    EventCandidate.objects.create(target=t_ep, nonlocalizedevent=nonlocalizedevent)
    alert_text = ALERT_TEXT_EP.format(nle_link=settings.NLE_LINKS[0][0], target_link=settings.TARGET_LINKS[0][0]
                                     ).format(nle=nonlocalizedevent, target=t_ep)

    # send SMS, Slack, and email alerts
    logger.info(f'Sending EP alert: {alert_text}')
    json_data = json.dumps({'text': alert_text}).encode('ascii')
    requests.post(settings.SLACK_EP_URL, data=json_data, headers={'Content-Type': 'application/json'})

    logger.info(f'Finished processing alert for {nonlocalizedevent.event_id}')

def handle_ice_cube_alert(message, metadata):
    alert = message.content
    logger.warning(f"Handling IceCube alert: {alert}")

    nonlocalizedevent, nle_created = NonLocalizedEvent.objects.get_or_create(
        event_id=alert['id'][0],
        event_type=NonLocalizedEvent.NonLocalizedEventType.NEUTRINO,
    )
    if nle_created:
        logger.info(f"Ingested a new Neutrion event with id {nonlocalizedevent.event_id} from IceCube alert stream")

    # create the localization from ra, dec, radius
    try:
        localization, skymap = create_elliptical_localization(
            nonlocalizedevent=nonlocalizedevent,
            center=[alert.get('ra'), alert.get('dec')], radius=alert.get('ra_dec_error'),
        )
    except Exception as e:
        localization = None
        skymap = None
        logger.error(f'Could not create EventLocalization for event: {nonlocalizedevent.event_id}. Exception: {e}')
        logger.error(traceback.format_exc())

    logger.debug(f"Storing IC alert: {alert}")

    # Now ingest the sequence for that event
    details = {key: alert.get(key) for key in
               ['instrument', 'nu_energy']}
    details['time'] = alert.get('trigger_time')  # to match IGWN alerts
    event_sequence, es_created = EventSequence.objects.update_or_create(
        nonlocalizedevent=nonlocalizedevent,
        localization=localization,
        sequence_id=nonlocalizedevent.sequences.count() + 1,
        details=details,
    )
    if es_created and localization is None:
        warning_msg = (
            f'{"Creating" if es_created else "Updating"} EventSequence without EventLocalization:'
            f'{event_sequence} for NonLocalizedEvent: {nonlocalizedevent}'
        )
        logger.warning(warning_msg)

    if CredibleRegionContour.objects.filter(localization=localization).exists():
        logger.info(f'Localization {localization.id} already exists')
    else:
        update_all_credible_region_percents_for_survey_fields(localization)
        if skymap is not None:
            skymap['PROBDENSITY'].unit = '1 / sr'
            calculate_credible_region(skymap, localization)
            calculate_footprint_probabilities(skymap, localization)
            rank_css_fields(localization.surveyfieldcredibleregions)
    ep_ra = alert.get('ra')
    ep_dec = alert.get('dec')
    ep_name = alert.get('event_name')
    t_ep = Target.objects.create(name=ep_name, type='SIDEREAL', ra=ep_ra, dec=ep_dec, permissions='PUBLIC')
    EventCandidate.objects.create(target=t_ep, nonlocalizedevent=nonlocalizedevent)
    alert_text = ALERT_TEXT_IC.format(nle_link=settings.NLE_LINKS[0][0], target_link=settings.TARGET_LINKS[0][0]
                                     ).format(nle=nonlocalizedevent, target=t_ep)

    # send SMS, Slack, and email alerts
    logger.info(f'Sending IceCube alert: {alert_text}')
    json_data = json.dumps({'text': alert_text}).encode('ascii')
    requests.post(settings.SLACK_IC_URL, data=json_data, headers={'Content-Type': 'application/json'})

    logger.info(f'Finished processing alert for {nonlocalizedevent.event_id}')


