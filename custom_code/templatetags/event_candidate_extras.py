"""
Some functions for accessing the EventCandidate table inside a django template
"""
import math
from functools import partial
from urllib.parse import urlparse
from django import template
from django.template.defaultfilters import linebreaks
from django.utils.safestring import mark_safe
from django.db.models import FloatField
from django.db.models.functions import Cast
from tom_nonlocalizedevents.models import EventCandidate, NonLocalizedEvent
from trove_targets.models import Target
from candidate_vetting.models import ScoreFactor
from candidate_vetting.vet_bns import (
    PARAM_RANGES as KN_PARAM_RANGES,
    PHOT_SCORE_MIN as KN_PHOT_SCORE_MIN
)
from astropy.units import Quantity

register = template.Library()

@register.simple_tag
def get_event_candidate_scores(event_candidates, *subscore_names):
    """Get the event candidate scores for everything in subscore_names

    event_candidates should be a django queryset of EventCandidate objects
    """ 

    ecs_out = []
    for ec in event_candidates:

        # first get all the subscores for this object
        subscores = ScoreFactor.objects.filter(
            event_candidate = ec,
            key__in = subscore_names
        ).annotate(
            value_float = Cast("value", FloatField())
        )

        
        # some of the keys in ScoreFactor are really just calculated values
        # where the score depends on the type of non-localized event. So we need to convert
        # these to scores.
        # I'm writing this just for KN for now, but we can modify as needed!
        val_not_score_keys = {
            "phot_peak_lum":"lum_max",
            "phot_peak_time":"peak_time",
            "phot_decay_rate":"decay_rate"
        }
        phot_score = 1
        subscore_keys = subscores.values_list("key", flat=True)        
        for subscore_key, param_range_key in val_not_score_keys.items():
            if subscore_key in subscore_names and subscore_key in subscore_keys:
                val = subscores.get(
                    key = subscore_key
                ).value_float

                val_max = max(KN_PARAM_RANGES[param_range_key])
                val_min = min(KN_PARAM_RANGES[param_range_key])
                if isinstance(val_min, Quantity):
                    val_min = val_min.value
                if isinstance(val_max, Quantity):
                    val_max = val_max.value
                
                if val < val_min or val > val_max:
                    phot_score *= KN_PHOT_SCORE_MIN
             
            
        subscores = subscores.exclude(
            key__in = list(val_not_score_keys.keys())
        ) # this removes those rows from the queryset
        
        # now we can compute the score just using multiplication
        subscore_list = list(
            subscores.values_list("value_float", flat=True)
        )
        subscore_list.append(phot_score)

        # save the score to a temporary field in the EventCandidate object
        ec.score = math.prod(subscore_list) # multiply the subscores
        ecs_out.append(ec)
        
    return sorted(ecs_out, reverse=True, key = lambda x : x.score)
    

#@register.inclusion_tag('tom_targets/partials/target_data.html', takes_context=True)
@register.simple_tag
def get_target_score(target_id):

    if target_id is None:
        return "Target ID is None!"

    target = Target.objects.get(id=target_id)

    out = {}
    for event_candidate in target.eventcandidate_set.all():
        nonlocalized_name = NonLocalizedEvent.objects.get(
            id = event_candidate.nonlocalizedevent_id
        ).event_id
        
        out[nonlocalized_name] = event_candidate.priority
    
    return out



@register.simple_tag
def display_score_details(target_id):

    if target_id is None:
        return "Target ID is None!"

    target = Target.objects.get(id=target_id)
    
    score_details = []
    for event_candidate in target.eventcandidate_set.all():
        score_details.append(event_candidate.scorefactor_set.all())

    res = {}
    keymap = dict(
        skymap_score = ("2D Localization Score", _float_format),
        host_distance_score = ("3D Association Score", _float_format),
        ps_score = ("Point Source Score (1 or 0)", _bool_format),
        mpc_score = ("Minor Planet Center Score (1 or 0)", _bool_format),
        agn_score = ("AGN Score (1 or 0 except for AGN flares)", _float_format),
        phot_peak_lum = ("Maximum Luminosity", partial(_sci_format, unit="erg/s")),
        phot_peak_time = ("Time of Maximum Light Curve", partial(_float_format, unit="days")),
        phot_decay_rate = ("Light Curve Slope (positive is brightening)", partial(_float_format, unit="mag/day"))
    )
    for queryset in score_details:
        for score_factor in queryset:
            nle = score_factor.event_candidate.nonlocalizedevent
            if nle not in res:
                res[nle] = ""
            if score_factor.key in keymap:
                label, fmter = keymap[score_factor.key]
            else:
                label = score_factor.key
                fmter = _float_format
            res[nle] += f"&emsp;{label}: {fmter(float(score_factor.value))}\n"

    out = ""
    for key, s in res.items():
        out += f"<h6>{key}</h6>"
        out += s
        out += "\n\n"
            
    return mark_safe(linebreaks(out))

def _float_format(flt, unit=""):
    return f"{flt:.2f} {unit}"

def _sci_format(flt, unit=""):
    prefactor, power = f"{flt:.2e}".split("e")
    if power[0] == "+":
        power = power[1:]
    return f"{prefactor} x 10<sup>{power}</sup> {unit}"

def _bool_format(flt):
    return int(flt)
