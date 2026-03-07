import logging
from requests import Response
from kne_cand_vetting.catalogs import static_cats_query
from kne_cand_vetting.galaxy_matching import galaxy_search
from kne_cand_vetting.survey_phot import TNS_get, query_ZTFpubphot
from kne_cand_vetting.mpc import minor_planet_match
from tom_targets.models import TargetExtra, TargetName
from tom_dataproducts.models import ReducedDatum
from tom_dataproducts.tasks import atlas_query
from tom_targets.models import Target
from tom_targets.utils import cone_search_filter
from slack_notifier.slack_notifier import SlackNotifier
from .templatetags.target_extras import split_name
import json
import numpy as np
from astropy.cosmology import FlatLambdaCDM
from astropy.time import Time, TimezoneInfo
from astropy.coordinates import SkyCoord
from astroquery.ipac.irsa.irsa_dust import IrsaDust
from healpix_alchemy.constants import HPX
from django.conf import settings
from django_tasks import task
import traceback

DB_CONNECT = "postgresql+psycopg2://{USER}:{PASSWORD}@{HOST}:{PORT}/{NAME}".format(**settings.DATABASES['default'])
COSMOLOGY = FlatLambdaCDM(H0=70., Om0=0.3)

logger = logging.getLogger(__name__)
new_format = logging.Formatter('[%(asctime)s] %(levelname)s : s%(message)s')
for handler in logger.handlers:
    handler.setFormatter(new_format)

def process_reduced_ztf_data(target, candidates):
    """Ingest data from the ZTF JSON format into ``ReducedDatum`` objects. Mostly copied from tom_base v2.13.0."""
    for candidate in candidates:
        if all([key in candidate['candidate'] for key in ['jd', 'magpsf', 'fid', 'sigmapsf']]):
            nondetection = False
        elif all(key in candidate['candidate'] for key in ['jd', 'diffmaglim', 'fid']):
            nondetection = True
        else:
            continue
        jd = Time(candidate['candidate']['jd'], format='jd', scale='utc')
        jd.to_datetime(timezone=TimezoneInfo())
        value = {
            'filter': {1: 'g', 2: 'r', 3: 'i'}[candidate['candidate']['fid']]
        }
        if nondetection:
            value['limit'] = candidate['candidate']['diffmaglim']
        else:
            value['magnitude'] = candidate['candidate']['magpsf']
            value['error'] = candidate['candidate']['sigmapsf']
        rd, created = ReducedDatum.objects.get_or_create(
            timestamp=jd.to_datetime(timezone=TimezoneInfo()),
            value=value,
            source_name='ZTF (SASSy)',
            data_type='photometry',
            target=target)
        if created:  # do this afterward, in case there are duplicate candidates with distinct ZIDs
            rd.source_location = candidate['zid']
            rd.save()


def update_or_create_target_extra(target, key, value):
    """
    Check if a ``TargetExtra`` with the given key exists for a given target. If it exists, update the value. If it does
    not exist, create it with the input value.
    """
    te, created = TargetExtra.objects.get_or_create(target=target, key=key)
    te.value = value
    te.save()


@task(queue_name="mpc")
def target_run_mpc(latest_det_id, _verbose=False):
    """check if a given photometric detection is a minor planet"""
    latest_det = ReducedDatum.objects.get(id=latest_det_id)
    match = minor_planet_match(latest_det.target.ra, latest_det.target.dec, Time(latest_det.timestamp).mjd)
    if match is not None:
        name, sep = match
        update_or_create_target_extra(latest_det.target, 'Minor Planet Match', name)
        update_or_create_target_extra(latest_det.target, 'Minor Planet Date', latest_det.timestamp)
        update_or_create_target_extra(latest_det.target, 'Minor Planet Offset', sep)
        logger.info(f'{latest_det.target.name} is {sep:.1f}" from minor planet {name}')
    else:
        update_or_create_target_extra(latest_det.target, 'Minor Planet Match', 'None')
        update_or_create_target_extra(latest_det.target, 'Minor Planet Date', latest_det.timestamp)
        logger.info(f"{latest_det.target.name} is not a minor planet!")


def vet_or_post_error(target, created=True, tns_time_limit: float=5., run_mpc=True, run_atlas=True, slack_client=None):
    """This hook runs following update of a target."""
    messages = []
    errors = []
    if created:
        # if the target has a TNS name, query the TNS API for updated coords, photometry, name, redshift, classification
        tns_objname = split_name(target.name)['tns_objname']
        if tns_objname is not None:
            get_obj = [("objname", tns_objname), ("objid", ""), ("photometry", "1"), ("spectra", "0")]
            response, time_to_wait = TNS_get(get_obj,
                                             settings.BROKERS['TNS']['bot_id'],
                                             settings.BROKERS['TNS']['bot_name'],
                                             settings.BROKERS['TNS']['api_key'],
                                             timelimit=tns_time_limit)

            if response is not None and response.status_code == 200:
                tns_reply = response.json()['data']

                # update the coordinates if needed; round to same number of sig figs as CSV files to avoid infinite loop
                tns_ra = float(f'{tns_reply["radeg"]:.14g}')
                tns_dec = float(f'{tns_reply["decdeg"]:.14g}')
                if target.ra != tns_ra or target.dec != tns_dec:
                    target.ra = tns_ra
                    target.dec = tns_dec
                    messages.append(f'Updated coordinates to {target.ra:.6f}, {target.dec:.6f} based on TNS')

                # ingest any photometry
                n_new_phot = 0
                for candidate in tns_reply.get('photometry', []):
                    jd = Time(candidate['jd'], format='jd', scale='utc')
                    value = {'filter': candidate['filters']['name']}
                    if candidate['flux']:  # detection
                        value['magnitude'] = float(candidate['flux'])
                    elif candidate['limflux']:  # nondetection
                        value['limit'] = float(candidate['limflux'])
                    else:  # something else, maybe an FRB; don't ingest it
                        continue
                    if candidate['fluxerr']:  # not empty or zero
                        value['error'] = float(candidate['fluxerr'])
                    rd, created = ReducedDatum.objects.get_or_create(
                        timestamp=jd.to_datetime(timezone=TimezoneInfo()),
                        value=value,
                        source_name=candidate['telescope']['name'] + ' (TNS)',
                        data_type='photometry',
                        target=target)
                    n_new_phot += created
                if n_new_phot:
                    messages.append(f'Added {n_new_phot:d} photometry points from the TNS')

                # if query is successful, use these up-to-date versions instead of what's in the local copy
                iau_name = tns_reply['name_prefix'] + tns_reply['objname']
                if target.name != iau_name:
                    target.name = iau_name
                    messages.append(f"Found a match in the TNS: {target.name}")

                classification = tns_reply['object_type']['name']
                if classification and target.extra_fields.get('Classification') != classification:
                    update_or_create_target_extra(target, 'Classification', classification)
                    messages.append(f"Classification set to {classification}")

                redshift = float(tns_reply['redshift']) if tns_reply['redshift'] else np.nan
                if np.isfinite(redshift) and target.extra_fields.get('Redshift') != redshift:
                    update_or_create_target_extra(target, 'Redshift', redshift)
                    messages.append(f"Redshift set to {redshift}")

                for alias in tns_reply['internal_names'].split(','):
                    if (alias and alias.replace(' ', '') != target.name.replace(' ', '')
                            and not TargetName.objects.filter(name=alias).exists()):
                        tn = TargetName.objects.create(target=target, name=alias)
                        messages.append(f'Added alias {tn.name} from TNS')

            else:
                if isinstance(response, Response):
                    tns_query_status = f"""
TNS Request for <https://wis-tns.org/object/{tns_objname}|{target.name}> responded with code {response.status_code}: {response.reason}
"""
                else:
                    tns_query_status = f'We ran out of API calls to the TNS with {time_to_wait}s left! This exceeded the {tns_time_limit}s limit!'
                logger.error(tns_query_status)
                errors.append(tns_query_status)
                if slack_client is not None:
                    slack_client.send_slack_message_from_text(text=tns_query_status)

        # always keep the galactic coordinates, healpix, and MW extinction up to date with updated coordinates
        coord = SkyCoord(target.ra, target.dec, unit='deg')
        target.galactic_lng = coord.galactic.l.deg
        target.galactic_lat = coord.galactic.b.deg
        update_or_create_target_extra(target=target, key='healpix', value=HPX.skycoord_to_healpix(coord))

        if target.extra_fields.get('MW E(B-V)') is None:
            try:
                mwebv = IrsaDust.get_query_table(coord, section='ebv')['ext SandF ref'][0]
            except Exception as e:
                logger.error(f'Error querying IRSA dust for {target.name}')
            else:
                update_or_create_target_extra(target, 'MW E(B-V)', mwebv)
                messages.append(f'MW E(B-V) set to {mwebv:.4f}')

        # crossmatch with local point-source and galaxy catalogs (local tns_results are ignored)
        qso, qoffset, asassn, asassnoffset, tns_results, gaia, gaiaoffset, gaiaclass, ps1prob, ps1, ps1offset = \
            static_cats_query([target.ra], [target.dec], db_connect=DB_CONNECT)

        update_or_create_target_extra(target=target, key='QSO Match', value=qso[0])
        if qso[0] != 'None':
            update_or_create_target_extra(target=target, key='QSO Offset', value=qoffset[0])

        update_or_create_target_extra(target=target, key='ASASSN Match', value=asassn[0])
        if asassn[0] != 'None':
            update_or_create_target_extra(target=target, key='ASASSN Offset', value=asassnoffset[0])

        update_or_create_target_extra(target=target, key='Gaia Match', value=gaia[0])
        if gaia[0] != 'None':
            update_or_create_target_extra(target=target, key='Gaia VS Offset', value=gaiaoffset[0])
            update_or_create_target_extra(target=target, key='Gaia VS Class', value=gaiaclass[0])

        update_or_create_target_extra(target=target, key='PS1 match', value=ps1[0])
        if ps1[0] != 'None' and ps1[0] != 'Multiple matches' and ps1[0] != 'Galaxy match':
            update_or_create_target_extra(target=target, key='PS1 Star Prob.', value=ps1prob[0])
            update_or_create_target_extra(target=target, key='PS1 Offset', value=ps1offset[0])

        matches, hostdict = galaxy_search(target.ra, target.dec, db_connect=DB_CONNECT)
        update_or_create_target_extra(target=target, key='Host Galaxies', value=json.dumps(hostdict))

        # set the initial guess for the transient distance, to make absolute magnitudes work automatically
        if target.distance is None:
            redshift = target.targetextra_set.filter(key='Redshift').first()
            if redshift is not None and redshift.float_value >= 0.02:  # from the transient redshift, if known
                messages.append(f'Updating distance of {target.name} based on redshift')
                target.distance = COSMOLOGY.luminosity_distance(redshift.float_value).to_value('Mpc')
            elif hostdict:  # otherwise from the most probable host
                dist = hostdict[0].get('Dist', np.nan)
                if np.isfinite(dist):
                    target.distance = dist
                disterr = hostdict[0].get('DistErr', np.nan)
                if np.all(np.isfinite(disterr)):
                    target.distance_err = np.mean(disterr)

        # ingest any ZTF photometry and internal names from SASSy; TODO: switch this to ANTARES
        ztfphot = query_ZTFpubphot(target.ra, target.dec, db_connect=DB_CONNECT)
        newztfphot = []
        if ztfphot:
            olddatetimes = [rd.timestamp for rd in target.reduceddatum_set.all()]
            for candidate in ztfphot:
                jd = Time(candidate['candidate']['jd'], format='jd', scale='utc')
                newdatetime = jd.to_datetime(timezone=TimezoneInfo())
                if newdatetime not in olddatetimes:
                    logger.info('New ZTF point at {0}.'.format(newdatetime))
                    newztfphot.append(candidate)
                if not TargetName.objects.filter(name=candidate['oid']).exists() and target.name != candidate['oid']:
                    tn = TargetName.objects.create(target=target, name=candidate['oid'])
                    messages.append(f'Added alias {tn.name} from ZTF')
        process_reduced_ztf_data(target, newztfphot)

        # only save once to avoid too many recursive calls to this function
        target.save()

        try:
            if run_mpc:
                detections = target.reduceddatum_set.filter(data_type="photometry", value__magnitude__isnull=False)
                if detections.exists():
                    target_run_mpc.enqueue(detections.latest().id)
            if run_atlas:
                mjd_now = Time.now().mjd
                atlas_query.enqueue(mjd_now - 20., mjd_now, target.id, 'atlas_photometry')
        except Exception as e:
            logger.error(''.join(traceback.format_exception(e)))
            error_message = f'Error vetting target {target.name}:\n{e}'
            errors.append(error_message)
            if slack_client is not None:
                slack_client.send_slack_message_from_text(error_message)

        # TODO: this is very temporary
        slack_m49 = SlackNotifier(slack_channel='alerts', token=settings.SLACK_TOKEN_TNS50)
        m49 = SkyCoord(187.6007, 8.4389, unit='deg')
        separation = coord.separation(m49).deg
        target_matches = cone_search_filter(Target.objects.exclude(id=target.id), coord.ra.deg, coord.dec.deg, 2. / 3600.)
        if separation <= 1.1 and not target_matches.exists():
            msg = f'<{settings.TARGET_LINKS[0][0]}|{{target.name}}> is {separation:.2f} deg from M49'.format(target=target)
            peak = target.reduceddatum_set.order_by('value__magnitude').first()
            if peak:
                peak_mag = peak.value['magnitude']
                msg += f" ({peak_mag:.1f} mag)"
                if peak_mag < 21.:
                    msg = '<!channel> ' + msg
            slack_m49.send_slack_message_from_text(msg)

    for message in messages:
        logger.info(message)

    return messages, errors
