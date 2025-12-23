"""
Some general functions useful for vetting photometry
"""
from typing import Tuple, Optional, Iterable
from datetime import datetime, timezone, timedelta

from astropy.time import Time
from astropy.stats import akaike_info_criterion_lsq as info_crit
from astropy import units as u
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit

from lightcurve_fitting.lightcurve import LC

from tom_nonlocalizedevents.models import NonLocalizedEvent, EventSequence
from tom_dataproducts.models import ReducedDatum
from trove_targets.models import Target
from candidate_vetting.public_catalogs.phot_catalogs import TNS_Phot
from candidate_vetting.tasks import async_atlas_query

def _powerlaw(x, a, y0):
    """
    Powerlaw that returns a logarithmic y value
    """
    return y0 - a * np.log10(x)

def _broken_powerlaw(x, a1, a2, y0, x0):
    """
    Broken powerlaw with smoothing s that returns a logarithmic y value
    """
    return y0 - np.log10((x/x0)**-a1 + (x/x0)**-a2)
    
def _ssr(model_y, data_y):
    """Sum of the squares of the residuals"""
    residuals = data_y - model_y
    return np.sum(residuals**2)

def _flux_to_lum(flux, lumdist):
    """convert flux to lum. Everything should be astropy quantities"""
    return 4 * np.pi * lumdist**2 * flux

def _get_phot(target_id:int, nonlocalized_event:NonLocalizedEvent) -> pd.DataFrame:
    """
    Get the photometry for this target_id and parse into a dataframe for further analysis
    """
    target = Target.objects.filter(id=target_id)[0]

    # get the photometry
    phot = list(ReducedDatum.objects.filter(target=target, data_type="photometry"))
        
    
    # clean up the photometry
    fordf = dict(
        telescope = [],
        mjd = [],
        mag = [],
        magerr = [],
        upperlimit = [],
        filter = [],
    )

    if len(phot) == 0:
        # just return an empty dataframe
        return pd.DataFrame(fordf)

    for p in phot:
        if hasattr(p, "source_name"):
            fordf["telescope"].append(p.source_name)
        elif "telescope" in p.value:
            fordf["telescope"].append(p.value["telescope"])
        else:
            fordf["telescope"].append("unknown")

        if not hasattr(p, "timestamp"): continue
        fordf["mjd"].append(Time(p.timestamp).mjd)

        if "filter" not in p.value: continue
        fordf["filter"].append(p.value["filter"])
        
        if "magnitude" in p.value:
            fordf["mag"].append(p.value["magnitude"])
            fordf["upperlimit"].append(False)
            if "error" in p.value:
                fordf["magerr"].append(p.value["error"])
            else:
                fordf["magerr"].append(0)
        elif "limit" in p.value:
            fordf["upperlimit"].append(True)
            fordf["mag"].append(p.value["limit"])
            fordf["magerr"].append(np.nan)
        else:
            continue

    fordf["filter"] = standardize_filter_names(fordf["filter"])
    
    photdf = pd.DataFrame(fordf)
    
    # clean out the 0's in the magerr column because it breaks the fitting
    # 2.5 / (3 * log(10)) is the constant 3 sigma uncertainty so let's assume this
    # as a worst case scenario
    photdf["magerr"] = photdf.magerr.replace(0, 2.5 / (3 * np.log(10)))

    # compute the days since the nonlocalized event passed in
    # get the GW event discovery date
    gw_disc_date = Time(
        EventSequence.objects.filter(
            nonlocalizedevent_id=nonlocalized_event.id
        ).last().details["time"]
    ).mjd
    
    # add a column to the dataframe
    photdf["dt"] = photdf.mjd - gw_disc_date

    return photdf

def _get_post_disc_phot(
        target_id:int,
        nonlocalized_event:NonLocalizedEvent,
        t_post:float=np.inf
) -> pd.DataFrame:
    photdf = _get_phot(target_id, nonlocalized_event)
    if not len(photdf):
        return 
    phot_post_disc = photdf[t_post >= photdf.dt >= 0]
    return phot_post_disc
    
def _get_pre_disc_phot(
        target_id:int,
        nonlocalized_event:NonLocalizedEvent
) -> pd.DataFrame:
    photdf = _get_phot(target_id, nonlocalized_event)
    if not len(photdf):
        return
    phot_pre_disc = photdf[photdf.dt < 0]
    return phot_pre_disc

def _get_window_stats(min_idx, max_idx, isdet):
    return int(sum(isdet[min_idx:max_idx])), int(len(isdet[min_idx:max_idx]))

def standardize_filter_names(
        filters:list[str],
        delimiters:list[str]=[".", "-", " "]
) -> list[str]:

    newfilters = []
    for filt in filters:
        newfilt = filt
        for delim in delimiters:
            newfilt = newfilt.split(delim)[0]
        newfilters.append(newfilt.strip())
    return newfilters
        
def estimate_max_find_decay_rate(
        dt_days:Iterable[float],
        mag:Iterable[float],
        magerr:Iterable[float],
        max_decay_fit_time:Optional[int]=25
) -> Tuple[float, float, float]:
    """
    Fit's both a single and broken powerlaw to the data, computes the AIC and then
    takes the "better" fit (lower AIC) and uses that to find an analytic time of maximum and decay
    rate over peak_time -> max_decay_fit_time. 
    
    PARAMETERS
    ---------
    dt_days: Iterable[float]
        A list/array of the days since the GW discovery. These should all be positive
    mag: Iterable[float]
        A list/array of the magnitudes since the GW discovery
    magerr: Iterable[float]
        A list/array of the magnitude errors since the GW discovery
    max_decay_fit_time: int
        The maximum time after the GW discovery in days that we should fit the decay to.
        The default is 25 days based on discussion from Rastinejad+2024.

    RETURNS
    -------
    max_time: float
        Days since GW discovery for max to occur
    decay_slope: float
        The slope of the decay from peak between peak and max_decay_fit_time if the
        if the data has a maximum in the mag array. Otherwise this is just the slope
        of the light curve in mag/day.
    """

    # define some useful variables
    pl_nparams = 2 # the degrees of freedom in a powerlaw model (m, y0, x0)
    bpl_nparams = 4 # the degrees of freedom in a broken powerlaw model (y0, x0, s, m1, m2)
    
    curve_fit_kwargs = dict(
        xdata = dt_days,
        ydata = mag,
        #sigma = magerr,
        absolute_sigma = True,
        maxfev = 5_000,
        ftol = 1e-8
    )
    
    # first fit a regular powerlaw
    try:
        pl_popt, pl_pcov = curve_fit(_powerlaw, **curve_fit_kwargs)
    except RuntimeError:
        # RuntimeError will throw if it doesn't converge
        pl_popt, pl_pcov = None, None
        
    # then fit a broken powerlaw
    # but we only want to try a broken powerlaw if there are more than 6 points
    # otherwise the data doesn't give enough constraining power
    # need to add 2 b/c otherwise we can't compute the AIC
    # For ref, the equation used in the AIC score is
    # aic = 2.0 * (n_params - log_likelihood) + 2.0 * n_params * (n_params + 1.0) / (
    #             n_samples - n_params - 1.0
    #         )
    # so if len(mag) = n_samples+1 the denominator is 0 and the AIC blows up
    if len(mag) > bpl_nparams+2: 
        bpl_bounds = [
            (-np.inf, 0), # a1 bound, can be anything
            (0, np.inf), # a2 bound, can be anything
            (0, 2*mag.max()), # y0 bound, really shouldn't be outside this range
            (0, dt_days.max()) # x0 bound, really shouldn't be greater than max(dt)
        ]
        try:
            bpl_popt, bpl_pcov = curve_fit(
                _broken_powerlaw,
                bounds=list(zip(*bpl_bounds)),
                **curve_fit_kwargs
            )
        except (RuntimeError, TypeError) as exc:
            # RuntimeError will throw if it doesn't converge
            # TypeError will throw if there are <5 photometry points (and we should be
            # using the single powerlaw anyways with so few points!)
            print(f"Failed on the Broken Powerlaw fit with {exc}")
            bpl_popt, bpl_pcov = None, None
    else:
        bpl_popt, bpl_pcov = None, None

    # define some variables for checking later if one of these methods failed
    pl_failed = pl_popt is None
    bpl_failed = bpl_popt is None
        
    # then calculate the reduced chi2 for each of these outputs
    # but we only need to do this if both models succeeded in fitting the data
    if not pl_failed and not bpl_failed:
        pl_model_y = _powerlaw(dt_days, *pl_popt)
        pl_ssr = _ssr(pl_model_y, mag)
        pl_info_crit = info_crit(pl_ssr, pl_nparams, len(mag))

        bpl_model_y = _broken_powerlaw(dt_days, *bpl_popt)
        bpl_ssr = _ssr(bpl_model_y, mag)
        bpl_info_crit = info_crit(bpl_ssr, bpl_nparams, len(mag))
        
    # now we can prefer the model with the lower AIC score
    if (not pl_failed and bpl_failed) or (pl_info_crit < bpl_info_crit and not pl_failed):
        print(f"Powerlaw fits better")
        model = _powerlaw
        best_fit_params = pl_popt
        decay_rate = pl_popt[0] # this is the slope
    elif not bpl_failed:
        print("Broken Powerlaw fits better")
        model = _broken_powerlaw
        best_fit_params = bpl_popt
        decay_rate = -bpl_popt[0] # this is the decay slope since we force -inf < a1 < 0 with the bounds, negate b/c magnitudes
    else:
        raise RuntimeError("Both a powerlaw and broken powerlaw failed to fit the data!")

    # finally, compute the maximum time using a finely spaced array
    # from min -> max of the dt_days array
    xtest = np.linspace(
        np.min(dt_days),
        np.max(dt_days),
        100*max_decay_fit_time
    )
    ytest = model(xtest, *best_fit_params)
    max_time = xtest[np.argmin(ytest)] # need to use min here b/s magnitudes are backwards
    
    return model, best_fit_params, max_time, decay_rate
    
def compute_peak_lum(
        mag:Iterable[float],
        magerr:Iterable[float],
        filters:Iterable[str],
        lumdist:u.Quantity,
        consider_err:bool=True
) -> float:    
    """
    Computes the peak luminosity (nu L_nu) for comparison with models

    Parameters
    ----------
    mag: Iterable[float]
        An array of magnitudes
    magerr: Iterable[float]
        An array of magnitude errors
    filters: Iterable[str]
        The telescope filters used for conversion to optical luminosity
    lumdist: float
        The luminosity distance to calculate the luminosity at as an astropy Quantity
    consider_err: bool
        It is possible that the peak magnitude has large uncertainties. To be
        conservative we can consider the 3-sigma uncertainty on the peak magnitude as
        the peak value to compute the luminosity for. Default is True (to be the most
        conservative with our cuts!)

    Returns
    -------
    The peak luminosity (nu L_nu) in erg/s
    """

    lc = LC([mag, magerr, filters], names=['mag', 'dmag', 'filter'])
    lc.calcFlux()

    if len(lc) == 0:
        return None # we don't want to change the score if there isn't photometry to do this
    
    # find the max of the light curve
    fluxmax_idx = np.argmax(lc["flux"])
    fluxmax = lc["flux"][fluxmax_idx]
    if consider_err:
        # turn the flux max into the 3 sigma upper error
        fluxmax += 3*lc["dflux"][fluxmax_idx]
    filtermax = lc["filter"][fluxmax_idx]
    
    # now convert that flux to a luminosity
    fluxmax = fluxmax*u.Unit("W/m^2/Hz")
    lummax = _flux_to_lum(fluxmax, lumdist).to("erg/s/Hz")

    # then we need to multiply be the effective frequency of the filter
    nu_lummax = (filtermax.freq_eff * lummax).to("erg/s")
    return nu_lummax

def get_predetection_stats(
        mjd:list[float],
        magerr:list[float],
        det_snr_thresh:int=5,
        window_size:int=5
) -> tuple[list[int],list[int]]:
    """
    Uses a sliding window to find all predetections within window_size and
    returns 1) a list of the number of predetections and 2) a list of the number
    of observations within that window

    Parameters
    ----------
    mjd: list[float]
        A list of the MJDs of the observations
    magerr: list[bool]
        A list the same length as mjd with the uncertainty on the magnitude. We use
        this with `det_snr_thresh` to determine if the observation is a detection
    det_thresh: int
        The required signal to noise ratio for a point to be considered a detection 
    window_size: int
        The window size in days. Default is 5.

    Returns
    -------
    Two lists: 1) the number of predetections in each window and 2) the number of
    observations in each window
    """

    # derive an array of if the observation is a detection
    isdet = ~np.isnan(magerr) * (magerr < 2.5 / (det_snr_thresh*np.log(10)))
    
    # sort both arrays according to the MJD
    sorted_idx = np.argsort(mjd)
    times = mjd[sorted_idx]
    isdet = isdet[sorted_idx]

    # now iterate from 0+window_size to end-window_size
    res = [
        _get_window_stats(
            np.where(times==times[i-window_size])[0][0],
            np.where(times==times[i+window_size])[0][0],
            isdet
        ) for i in range(0+window_size, len(isdet)-window_size, 1)
    ]
    
    # now we can transpose the result and return
    return tuple(zip(*res))

def find_public_phot(
        target:Target,
        forced_phot_tol=1,
        days_ago_max=200,
        queue_priority=100
) -> None:
    """Query TNS, ATLAS Forced photometry, and other services for publicly available
    photometry. After querying for new photometry it will automatically add it to
    the target.

    Parameters
    ----------
    target: Target
        The Trove Target model object to find data for
    forced_phot_tol: int = 1
        The tolerance on the forced photometry sources. If we have queried for forced
        photometry in the past forced_phot_tol days, we skip querying for more.
    days_ago_max: int = 200
        The days ago to query forced photometry servers for. If forced photometry
        already exists from a service within days_ago, we only query for the days since
        the last existing photometry point.
    """

    # check TNS for any new photometry
    TNS_Phot("tns").query(target, timelimit=10)

    # query ATLAS for new forced photometry
    # get the most recent ATLAS forced photometry point
    atlas_data = target.reduceddatum_set.filter(
        data_type="photometry",
        source_name="ATLAS"
    )
    query_atlas = True
    days_ago = days_ago_max # initialize days_ago as the maximum, and recompute as needed
    if atlas_data.count(): # if this is true there is existing ATLAS data
        last_atlas_point = atlas_data.order_by("timestamp").last()

        now = datetime.now(tz=timezone.utc)
        if last_atlas_point.timestamp < now - timedelta(days=forced_phot_tol):
            # then we should only query ATLAS for this target for forced photometry
            # since the last point we have
            days_ago = (last_atlas_point.timestamp - now).days
            query_atlas = days_ago > 3 # otherwise ATLAS probably won't have anything new
        else:
            # Then we have already queried ATLAS for this target in the past forced_phot_tol days
            query_atlas = False
            
    if query_atlas:
        async_atlas_query.using(
            priority=queue_priority # this sets the priority to whatever is passed in
        ).enqueue(
            target.id,
            days_ago=min(
                days_ago_max,
                days_ago
            ) # this min ensures we never query more than days_ago_max
        )
