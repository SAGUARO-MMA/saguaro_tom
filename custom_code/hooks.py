import logging
from requests import Response

from candidate_vetting.vet import (
    host_association,
    point_source_association,
    agn_association_2d
)
from candidate_vetting.public_catalogs.phot_catalogs import TNS_Phot
from trove_mpc import Transient

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


@task(queue_name="mpc", priority=settings.PRIORITY_MID)
def target_run_mpc(latest_det_id, _verbose=False):
    """check if a given photometric detection is a minor planet"""
    latest_det = ReducedDatum.objects.get(id=latest_det_id)
    
    date = Time(latest_det.timestamp).mjd
    t = Transient(latest_det.target.ra, latest_det.target.dec)
    mpc_match = t.minor_planet_match(date)
    
    if mpc_match is not None:
        update_or_create_target_extra(latest_det.target, 'Minor Planet Match', mpc_match.match_name)
        update_or_create_target_extra(latest_det.target, 'Minor Planet Date', latest_det.timestamp)
        update_or_create_target_extra(latest_det.target, 'Minor Planet Offset', mpc_match.distance)
        logger.info(f'{latest_det.target.name} is {mpc_match.distance}" from minor planet {mpc_match.match_name}')
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

            # check TNS for new photometry
            _, response, time_to_wait = TNS_Phot("tns").query(target, timelimit=tns_time_limit)

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
        host_df = host_association(target.id)
        agn_df = agn_association_2d(target.id)
        ps_matches = point_source_association(target.id)
        
        if "AsassnQ3C" in ps_matches:
            asassn = ps_matches["AsassnQ3C"][0]
            asassnoffset = ps_matches["AsassnQ3C"][1]
            update_or_create_target_extra(target=target, key='ASASSN Match', value=asassn[0])
            update_or_create_target_extra(target=target, key='ASASSN Offset', value=asassnoffset[0])
        else:    
            update_or_create_target_extra(target=target, key='ASASSN Match', value="None")

        if "Gaiadr3VariableQ3C" in ps_matches:
            gaia = ps_matches["Gaiadr3VariableQ3C"][0]
            gaiaoffset = ps_matches["Gaiadr3VariableQ3C"][1]
            update_or_create_target_extra(target=target, key='Gaia Match', value=gaia[0])
            update_or_create_target_extra(target=target, key='Gaia VS Offset', value=gaiaoffset[0])
        else:
            update_or_create_target_extra(target=target, key='Gaia Match', value="None")            
            
        if "Ps1Q3C" in ps_matches:
            gaia = ps_matches["Ps1Q3C"][0]
            gaiaoffset = ps_matches["Ps1Q3C"][1]
            update_or_create_target_extra(target=target, key='PS1 Match', value=gaia[0])
            update_or_create_target_extra(target=target, key='PS1 Offset', value=gaiaoffset[0])
        else:
            update_or_create_target_extra(target=target, key='PS1 Match', value="None")

            
        # set the initial guess for the transient distance, to make absolute magnitudes work automatically
        if target.distance is None:
            redshift = target.targetextra_set.filter(key='Redshift').first()
            if redshift is not None and redshift.float_value >= 0.02:  # from the transient redshift, if known
                messages.append(f'Updating distance of {target.name} based on redshift')
                target.distance = settings.COSMO.luminosity_distance(redshift.float_value).to_value('Mpc')
            elif len(host_df):  # otherwise from the most probable host
                dist = host_df.lumdist.values[0]
                disterr = host_df.lumdist_err.values[0]
                if np.isfinite(dist) and np.all(np.isfinite(disterr)):
                    target.distance = dist
                    target.distance_err = np.mean(disterr)

        # only save once to avoid too many recursive calls to this function
        target.save()

        try:
            if run_mpc:
                detections = target.reduceddatum_set.filter(data_type="photometry", value__magnitude__isnull=False)
                if detections.exists():
                    target_run_mpc.enqueue(detections.latest().id)
            if run_atlas:
                mjd_now = Time.now().mjd
                atlas_query.using(
                    priority=settings.PRIORITY_LOW
                ).enqueue(
                    mjd_now - 20.,
                    mjd_now,
                    target.id,
                    'atlas_photometry'
                )
        except Exception as e:
            logger.error(''.join(traceback.format_exception(e)))
            error_message = f'Error vetting target {target.name}:\n{e}'
            errors.append(error_message)
            if slack_client is not None:
                slack_client.send_slack_message_from_text(error_message)

    for message in messages:
        logger.info(message)

    return messages, errors
