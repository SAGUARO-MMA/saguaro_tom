import logging
import warnings

from candidate_vetting.vet import (
    host_association,
    point_source_association,
    agn_association_2d,
    evcc_galaxy_check,)


from candidate_vetting.public_catalogs.phot_catalogs import TNS_Phot
from trove_mpc import Transient

from tom_targets.models import TargetExtra, TargetName
from tom_dataproducts.models import PhotometryReducedDatum
from tom_dataproducts.tasks import atlas_query
from tom_antares.antares import AntaresDataService
from .templatetags.target_extras import split_name
import json
import numpy as np
from astropy.time import Time
from astropy.coordinates import SkyCoord
from astroquery.ipac.irsa.irsa_dust import IrsaDust
from healpix_alchemy.constants import HPX
from django.conf import settings
from django_tasks import task
import traceback

logger = logging.getLogger(__name__)
# new_format = logging.Formatter('[%(asctime)s] %(levelname)s : s%(message)s')
# for handler in logger.handlers:
#    handler.setFormatter(new_format)


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
    latest_det = PhotometryReducedDatum.objects.get(id=latest_det_id)

    date = Time(latest_det.timestamp).mjd
    t = Transient(latest_det.target.ra, latest_det.target.dec)
    mpc_match = t.minor_planet_match(date)

    if mpc_match is not None:
        update_or_create_target_extra(
            latest_det.target, "Minor Planet Match", mpc_match.match_name
        )
        update_or_create_target_extra(
            latest_det.target, "Minor Planet Date", latest_det.timestamp
        )
        update_or_create_target_extra(
            latest_det.target, "Minor Planet Offset", mpc_match.distance
        )
        logger.info(
            f'{latest_det.target.name} is {mpc_match.distance}" from minor planet {mpc_match.match_name}'
        )
    else:
        update_or_create_target_extra(latest_det.target, "Minor Planet Match", "None")
        update_or_create_target_extra(
            latest_det.target, "Minor Planet Date", latest_det.timestamp
        )
        logger.info(f"{latest_det.target.name} is not a minor planet!")


def vet_or_post_error(
    target,
    created=True,
    tns_time_limit: float = 5.0,
    run_mpc=False,
    run_atlas=True,
    slack_client=None,
):
    """This hook runs following update of a target."""
    messages = []
    errors = []
    if created:
        # if the target has a TNS name, query the TNS API for updated coords, photometry, name, redshift, classification
        tns_objname = split_name(target.name)["tns_objname"]
        if tns_objname is not None:
            # check TNS for new photometry
            n_new_phot, tns_reply = TNS_Phot("tns").query(target, timelimit=tns_time_limit)
            if tns_reply:
                if n_new_phot:
                    messages.append(
                        f"Added {n_new_phot:d} photometry points from the TNS"
                    )

                # if query is successful, use these up-to-date versions instead of what's in the local copy
                iau_name = tns_reply["name_prefix"] + tns_reply["objname"]
                if target.name != iau_name:
                    target.name = iau_name
                    messages.append(f"Found a match in the TNS: {target.name}")

                classification = tns_reply["object_type"]["name"]
                if (
                    classification
                    and target.extra_fields.get("Classification") != classification
                ):
                    update_or_create_target_extra(
                        target, "Classification", classification
                    )
                    messages.append(f"Classification set to {classification}")

                redshift = (
                    float(tns_reply["redshift"]) if tns_reply["redshift"] else np.nan
                )
                if (
                    np.isfinite(redshift)
                    and target.extra_fields.get("Redshift") != redshift
                ):
                    update_or_create_target_extra(target, "Redshift", redshift)
                    messages.append(f"Redshift set to {redshift}")

                for alias in tns_reply["internal_names"].split(","):
                    if (
                        alias
                        and alias.replace(" ", "") != target.name.replace(" ", "")
                        and not TargetName.objects.filter(name=alias).exists()
                    ):
                        tn = TargetName.objects.create(target=target, name=alias)
                        messages.append(f"Added alias {tn.name} from TNS")

        # always keep the galactic coordinates, healpix, and MW extinction up to date with updated coordinates
        coord = SkyCoord(target.ra, target.dec, unit="deg")
        target.galactic_lng = coord.galactic.l.deg
        target.galactic_lat = coord.galactic.b.deg
        update_or_create_target_extra(
            target=target, key="healpix", value=HPX.skycoord_to_healpix(coord)
        )

        if target.extra_fields.get("MW E(B-V)") is None:
            try:
                mwebv = IrsaDust.get_query_table(coord, section="ebv")["ext SandF ref"][
                    0
                ]
            except Exception as e:
                logger.error(f"Error querying IRSA dust for {target.name}")
            else:
                update_or_create_target_extra(target, "MW E(B-V)", mwebv)
                messages.append(f"MW E(B-V) set to {mwebv:.4f}")

        # crossmatch with local point-source and galaxy catalogs (local tns_results are ignored)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            host_df = host_association(target.id)
            agn_df = agn_association_2d(target.id)
            ps_matches = point_source_association(target.id)

            # geometric association with nearby Virgo (EVCC) galaxies.

            try:
                evcc_matches = json.loads(evcc_galaxy_check(target.id))
            except Exception as e:
                logger.error(f"EVCC check failed for {target.name}: {e}")
                evcc_matches = []

            if evcc_matches:
                names = ", ".join(m["ID"] for m in evcc_matches)
                messages.append(f"Within Kron radius of EVCC galaxy: {names}")

                g = evcc_matches[0]  # closest
                try:
                    target_url = settings.TARGET_LINKS[0][0].format(target=target)
                    evcc_slack = SlackNotifier(
                        slack_channel="nearby-galaxy-alerts",
                        token=settings.SLACK_TOKEN_TNS50,
                    )
                    evcc_slack.send_slack_message_from_text(
                        f":telescope: *{target.name}* is {g['OffsetKron']}x Kron from Virgo "
                        f"galaxy *{g['ID']}* (offset {g['Offset']}\", r (galaxy mag) ={g['rMag']}, "
                        f"type {g['Type']}, cz={g['cz']} km/s). "
                        f"Nearby-galaxy transient — please inspect. "
                        f"<{target_url}|View target>"
                    )
                except Exception as e:
                    logger.error(f"EVCC Slack alert failed for {target.name}: {e}")


        if "AsassnQ3C" in ps_matches:
            asassn = ps_matches["AsassnQ3C"][0]
            asassnoffset = ps_matches["AsassnQ3C"][1]
            update_or_create_target_extra(
                target=target, key="ASASSN Match", value=asassn[0]
            )
            update_or_create_target_extra(
                target=target, key="ASASSN Offset", value=asassnoffset[0]
            )
        else:
            update_or_create_target_extra(
                target=target, key="ASASSN Match", value="None"
            )

        if "Gaiadr3VariableQ3C" in ps_matches:
            gaia = ps_matches["Gaiadr3VariableQ3C"][0]
            gaiaoffset = ps_matches["Gaiadr3VariableQ3C"][1]
            update_or_create_target_extra(
                target=target, key="Gaia Match", value=gaia[0]
            )
            update_or_create_target_extra(
                target=target, key="Gaia VS Offset", value=gaiaoffset[0]
            )
        else:
            update_or_create_target_extra(target=target, key="Gaia Match", value="None")

        if "Ps1Q3C" in ps_matches:
            gaia = ps_matches["Ps1Q3C"][0]
            gaiaoffset = ps_matches["Ps1Q3C"][1]
            update_or_create_target_extra(target=target, key="PS1 Match", value=gaia[0])
            update_or_create_target_extra(
                target=target, key="PS1 Offset", value=gaiaoffset[0]
            )
        else:
            update_or_create_target_extra(target=target, key="PS1 Match", value="None")

        # set the initial guess for the transient distance, to make absolute magnitudes work automatically
        if target.distance is None:
            redshift = target.targetextra_set.filter(key="Redshift").first()
            if (
                redshift is not None and redshift.float_value >= 0.02
            ):  # from the transient redshift, if known
                messages.append(f"Updating distance of {target.name} based on redshift")
                target.distance = settings.COSMO.luminosity_distance(
                    redshift.float_value
                ).to_value("Mpc")
            elif len(host_df):  # otherwise from the most probable host
                dist = host_df.lumdist.values[0]
                disterr = host_df.lumdist_err.values[0]
                if np.isfinite(dist) and np.all(np.isfinite(disterr)):
                    target.distance = dist
                    target.distance_err = np.mean(disterr)

            # ingest any ZTF or LSST photometry and internal names from ANTARES
            data_service = AntaresDataService()
            data = data_service.query_reduced_data(target)
            data_service.to_reduced_datums(target, data)
            alias_data = data_service.query_aliases(target=target)
            data_service.to_aliases(target, alias_data)

        # only save once to avoid too many recursive calls to this function
        target.save()

        try:
            if run_mpc:
                detections = target.photometryreduceddatum_set.filter(brightness__isnull=False)
                if detections.exists():
                    target_run_mpc.enqueue(detections.latest().id)
            if run_atlas:
                mjd_now = Time.now().mjd
                last_atlas_point_mjd = _get_last_atlas_point_date(target)

                if _should_run_atlas_fp(last_atlas_point_mjd, mjd_now - 14):
                    logger.debug("No ATLAS photometry in the past 14 days")
                    # only run ATLAS FP if we haven't run it already in the past two weeks
                    # and then only run it for the last 20 days
                    # since a user can always request additional ATLAS FP if needed
                    min_atlas_fp_mjd = _derive_atlas_lower_mjd(
                        last_atlas_point_mjd, mjd_now - 20
                    )

                    logger.debug(
                        f"Running ATLAS FP from {min_atlas_fp_mjd} until today"
                    )

                    atlas_query.using(priority=settings.PRIORITY_LOW).enqueue(
                        min_atlas_fp_mjd, mjd_now, target.id, "atlas_photometry"
                    )
                else:
                    logger.debug(
                        "ATLAS photometry found in the past 14 days, not running ATLAS FP!"
                    )

        except Exception as e:
            logger.error("".join(traceback.format_exception(e)))
            error_message = f"Error vetting target {target.name}:\n{e}"
            errors.append(error_message)
            if slack_client is not None:
                slack_client.send_slack_message_from_text(error_message)

    for message in messages:
        logger.info(message)

    return messages, errors


def _get_last_atlas_point_date(target):
    atlas_data = target.photometryreduceddatum_set.filter(source_name="ATLAS")

    if atlas_data.count():
        last_atlas_point = atlas_data.order_by("timestamp").last()
        return Time(last_atlas_point.timestamp).mjd

    return


def _should_run_atlas_fp(last_atlas_point_mjd, min_mjd):
    """Return True if the last ATLAS FP point stored is before min_mjd"""
    return last_atlas_point_mjd is None or last_atlas_point_mjd < min_mjd


def _derive_atlas_lower_mjd(last_atlas_point_mjd, min_mjd):

    if last_atlas_point_mjd is not None and last_atlas_point_mjd > min_mjd:
        return last_atlas_point_mjd

    return min_mjd
