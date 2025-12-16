"""
The "pipeline" to vet candidate counterparts to nonlocalized events based on 
their resemblance to kilonovae.
"""
import logging
from typing import Optional
from astropy.time import Time
from astropy import units as u
import pandas as pd
import numpy as np

from .vet import (
    skymap_association,
    point_source_association,
    host_association,
    host_distance_match,
    associate_agn_2d,
    agn_distance_match,
    update_score_factor,
)
from .vet_phot import (
    _get_post_disc_phot,
    _score_phot,
    _get_pre_disc_phot,
    get_predetection_stats,
    PHOT_SCORE_MIN,
    PREDETECTION_SNR_THRESHOLD
)
from trove_mpc import Transient

from trove_targets.models import Target
from tom_dataproducts.models import ReducedDatum
from tom_nonlocalizedevents.models import (
    EventCandidate,
    NonLocalizedEvent,
    EventSequence
)

logger = logging.getLogger(__name__)

PARAM_RANGES = dict(
    lum_max = [0*u.erg/u.s, 1e43*u.erg/u.s],
    peak_time = [0, 4],
    decay_rate = [-np.inf, -0.1],
    max_predets = 3,
    t_pre = 0,
)


def vet_bns(target_id:int, nonlocalized_event_name:Optional[str]=None):

    # get the correct EventCandidate object for this target_id and nonlocalized event
    nonlocalized_event = NonLocalizedEvent.objects.get(
        event_id=nonlocalized_event_name
    )
    event_candidate = EventCandidate.objects.get(
        nonlocalizedevent_id = nonlocalized_event.id,
        target_id = target_id
    )
    
    ## check skymap association
    skymap_score = skymap_association(nonlocalized_event_name, target_id)
    update_score_factor(event_candidate, "skymap_score", skymap_score)
    if skymap_score < 1e-2:
        return 

    ## run the point source checker
    ps_score = point_source_association(target_id)
    update_score_factor(event_candidate, "ps_score", ps_score)
    
    ## AGN score
    # search for an AGN associated with the target
    agn_df = associate_agn_2d(
        target_id, 
        radius=2 # 2 arcseconds
    )
    # then, assign score based on AGN association
    if len(agn_df) != 0:
        agn_assoc_score = 0 # for BNS, association with an AGN is bad
    else:
        agn_assoc_score = 1 
    agn_score = agn_assoc_score # for BNS, don't bother with 3D AGN scoring
    update_score_factor(event_candidate, "agn_score", agn_score)
    
    ## if either point source or AGN score is 0, end it here
    if ps_score == 0 or agn_score == 0:
        return
    
    ## run the minor planet checker
    target = Target.objects.filter(id=target_id)[0]
    phot = ReducedDatum.objects.filter(
        target_id=target_id,
        data_type="photometry",
        value__magnitude__isnull=False
    )
    if phot.exists():
        latest_det = phot.latest()
        date = Time(latest_det.timestamp).mjd
        t = Transient(target.ra, target.dec)
        mpc_match = t.minor_planet_match(date)
    else:
        logger.warn("This candidate has no photometry, skipping MPC!")
        mpc_match = None

    # update the score factor information
    if mpc_match is not None:
        update_score_factor(event_candidate, "mpc_match_name", mpc_match.match_name)
        update_score_factor(event_candidate, "mpc_match_sep", mpc_match.distance)
        update_score_factor(event_candidate, "mpc_match_date", latest_det.timestamp)
        mpc_score = 0
        update_score_factor(event_candidate, "mpc_score", mpc_score)
        return
    else:    
        mpc_score = 1
        update_score_factor(event_candidate, "mpc_score", mpc_score)

    ## distance score
    # do the Pcc analysis and find a host
    host_df = host_association(
        target_id,
        radius = 5*60 # 5*60 arcseconds
    )
    if len(host_df) != 0:
        # then run the distance comparison for each of these hosts
        host_df = host_distance_match(
            host_df,
            target_id,
            nonlocalized_event_name
        )

        # choose the maximum score out of the top 10 best hosts
        host_score = host_df.dist_norm_joint_prob.max()
        update_score_factor(event_candidate, "host_distance_score", host_score)

    else:
        # if no hosts are found we don't want to bias the final score if the host
        # is just too far
        host_score = 1
        
    ## photometry scoring
    allphot = _get_post_disc_phot(target_id=target_id, nonlocalized_event=nonlocalized_event)
    phot_score, lum, max_time, decay_rate, _, _ = _score_phot(
        allphot=allphot,
        target = target,
        nonlocalized_event = nonlocalized_event,
        param_ranges=PARAM_RANGES,
        filt = ["g", "r", "i", "o", "c"] # use the common optical filters
    )
    if lum is not None:
        update_score_factor(event_candidate, "phot_peak_lum", lum.value)
    if max_time is not None:
        update_score_factor(event_candidate, "phot_peak_time", max_time)
    if decay_rate is not None:
        update_score_factor(event_candidate, "phot_decay_rate", decay_rate)

    # check for *reliable* predetections before time t_pre
    prephot = _get_pre_disc_phot(target.id,
                                 nonlocalized_event, 
                                 PARAM_RANGES["t_pre"])
    predet_score = 1
    if prephot is not None and len(prephot):
        try:
            n_predets, _ = get_predetection_stats(
                prephot.mjd.values,
                prephot.magerr.values,
                window_size=5, # +/-5 day window size
                det_snr_thresh=PREDETECTION_SNR_THRESHOLD
            )
        except ValueError:
            n_predets = [0] # this ValueError only happens when there aren't any predets
        if any(v >= PARAM_RANGES["max_predets"] for v in n_predets):
            predet_score = PHOT_SCORE_MIN
            update_score_factor(event_candidate, "predetection_score", predet_score)
