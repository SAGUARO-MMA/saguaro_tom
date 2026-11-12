from django import template
from django.template.defaultfilters import stringfilter
from astropy.coordinates import SkyCoord
from guardian.shortcuts import get_objects_for_user
from tom_targets.models import TargetList
import json
import re

register = template.Library()

TNS_PREFIXES = ["AT", "SN", "TDE", "FRB"]


@register.filter
def ecliptic_lng(target):
    sc = SkyCoord(target.ra, target.dec, unit='deg')
    return sc.barycentrictrueecliptic.lon.deg


@register.filter
def ecliptic_lat(target):
    sc = SkyCoord(target.ra, target.dec, unit='deg')
    return sc.barycentrictrueecliptic.lat.deg


@register.filter
@stringfilter
def split_name(name):
    """Splits the name into a prefix, consisting of no digits, and a basename, which starts with its first digit"""
    res = re.match(r'(?P<prefix>\D*)(?P<basename>.*)', name)
    name_info = res.groupdict()
    if name_info['prefix'] == 'FRB':
        name_info['tns_objname'] = name
    elif name_info['prefix'] in TNS_PREFIXES:
        name_info['tns_objname'] = name_info['basename']
    else:
        name_info['tns_objname'] = None
    return name_info


@register.inclusion_tag('tom_targets/partials/aladin_custom.html')
def aladin_custom(target):
    """
    Displays Aladin skyview of the given target along with basic finder chart annotations and circles around potential
    host galaxies. The resulting image is downloadable. This templatetag only works for sidereal targets.
    """
    target_extra = target.targetextra_set.filter(key='Host Galaxies')
    if target_extra.exists():
        galaxies = json.loads(target_extra.first().value)
    else:
        galaxies = []
    return {'target': target, 'galaxy_ras': [g['RA'] for g in galaxies], 'galaxy_decs': [g['Dec'] for g in galaxies]}

@register.filter
def parse_json_str(value):
    return json.loads(value)


@register.inclusion_tag('custom_code/partials/target_groups.html', takes_context=True)
def manage_target_groups(context, target):
    """
    Lists the groups this target is in, with a Remove button for each, plus a dropdown and button
    to add the target to any other group the user can modify.
    """
    groups = TargetList.objects.filter(targets=target)
    available_groups = get_objects_for_user(context['user'], 'tom_targets.change_targetlist') \
        .exclude(pk__in=groups).order_by('name')
    return {'target': target, 'groups': groups, 'available_groups': available_groups,
            'user': context['user'], 'csrf_token': context.get('csrf_token')}
