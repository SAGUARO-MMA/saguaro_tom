from django import template
from django.conf import settings
from guardian.shortcuts import get_objects_for_user
from tom_observations.models import DynamicCadence

register = template.Library()


@register.filter
def display_obs_type(value):
    """
    This converts SAMPLE_TITLE into Sample Title. Used for display all-caps observation type in the
    tabs as titles.
    """
    title = value.replace('_', ' ')
    if value.isupper():
        title = title.title()
    return title

@register.inclusion_tag('tom_observations/partials/observation_sequence_list.html', takes_context=True)
def observation_sequence_list(context, target=None):
    """
    Displays a list of all observations in the TOM, limited to an individual target if specified.
    """
    if target:
        if settings.TARGET_PERMISSIONS_ONLY:
            obs_sequences = DynamicCadence.objects.filter(observation_group__observation_records__target=target
                                                            ).distinct()
        else:
            obs_records = get_objects_for_user(
                                context['request'].user,
                                'tom_observations.view_observationrecord'
                            ).filter(target=target)
            obs_sequences = DynamicCadence.objects.filter(observation_group__observation_records__in=obs_records
                                                          ).distinct()
    else:
        obs_sequences = DynamicCadence.objects.all()
    return {'observation_sequences': obs_sequences.order_by('-created'),
            'params_to_hide': ['start', 'end', 'name', 'jitter', 'period', 'facility', 'target_id', 'guider_mode',
                               'max_lunar_phase', 'cadence_strategy', 'observation_type', 'cadence_frequency',
                               'optimization_type', 'min_lunar_distance', 'guider_exposure_time',
                               'configuration_repeats', 'fractional_ephemeris_rate']}
