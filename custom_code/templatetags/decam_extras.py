"""
Template tags specifically for DECam candidates.
"""

from django import template
from django.urls import reverse
import logging

register = template.Library()
logger = logging.getLogger(__name__)


@register.filter
def decam_thumbnail_url(candidate, suffix):
    """
    Returns thumbnail URL for DECam candidates from database.
    
    Usage in template:
        <img src="{{ candidate|decam_thumbnail_url:'science' }}">
    """
    suffix_map = {
        'template': 'template',
        'science': 'science',
        'difference': 'difference',
        'ref': 'template',
        'img': 'science',
        'diff': 'difference',
    }
    
    thumb_type = suffix_map.get(suffix, suffix)
    
    try:
        return reverse('custom_code:decam_thumbnail', kwargs={
            'candidate_id': candidate.id,
            'thumb_type': thumb_type,
        })
    except Exception as e:
        logger.error(f'Error generating DECam thumbnail URL: {e}')
        return ''

@register.inclusion_tag('tom_targets/partials/decam_candidates_table.html')
def decam_candidates_table(target):
    """
    Display DECam candidates for a target.
    
    Usage in template:
        {% decam_candidates_table target %}
    """
    from custom_code.models import DecamCandidate
    
    decam_candidates = DecamCandidate.objects.filter(
        target=target
    ).select_related(
        'observation_record',
        'observation_record__survey_field'
    ).order_by('mjd_obs', 'filter_name')
    
    return {'decam_candidates': decam_candidates}
