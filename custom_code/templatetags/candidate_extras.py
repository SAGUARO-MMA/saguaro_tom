"""
Template tags for displaying candidate thumbnails.

This module handles thumbnail URLs for both:
- CSS candidates: Served from external URL (sassy.as.arizona.edu)
- DECam candidates: Served from database via Django view
"""

from django import template
from django.urls import reverse
import logging

register = template.Library()
logger = logging.getLogger(__name__)


@register.filter
def thumbnail_url(candidate, suffix):
    """
    Returns an image thumbnail URL based on the candidate's facility.
    
    For CSS candidates: Returns URL to sassy.as.arizona.edu
    For DECam candidates: Returns URL to Django view that serves from database
    
    Parameters
    ----------
    candidate : Candidate
        The candidate object
    suffix : str
        Thumbnail type: 
            CSS: 'img', 'ref', 'diff', 'scorr'
            DECam: 'template', 'science', 'difference'
    
    Returns
    -------
    str
        URL to the thumbnail image
    
    Usage in template:
        <img src="{{ candidate|thumbnail_url:'diff' }}">
    """
    # Check facility (default to CSS for backwards compatibility)
    facility = getattr(candidate, 'facility', 'CSS')
    
    if facility == 'DECam':
        return decam_thumbnail_url(candidate, suffix)
    else:
        return css_thumbnail_url(candidate, suffix)


def css_thumbnail_url(candidate, suffix):
    """
    Returns CSS thumbnail URL from sassy.as.arizona.edu.
    
    This is the original implementation for CSS candidates.
    """
    try:
        visit = candidate.observation_record.observation_id.split('_')[4]
        url = f'http://sassy.as.arizona.edu/papp/api/{candidate.observation_record.scheduled_start.strftime("%Y/%m/%d")}/'
        url += f'{candidate.observation_record.survey_field}/{candidate.candidatenumber}_{visit}_{suffix}.png'
        return url
    except Exception as e:
        logger.error(f'Error generating CSS thumbnail URL: {e}')
        return ''


def decam_thumbnail_url(candidate, suffix):
    """
    Returns URL to serve DECam thumbnail from database.
    
    Maps CSS-style suffix names to DECam thumbnail types.
    Note: DECam doesn't have 'scorr' - returns empty string for that.
    """
    # Map CSS-style suffixes to DECam thumbnail types
    suffix_map = {
        # DECam native names
        'template': 'template',
        'science': 'science',
        'difference': 'difference',
        # CSS-style aliases (used in templates)
        'ref': 'template',
        'img': 'science',
        'diff': 'difference',
        'sci': 'science',
    }
    
    # DECam doesn't have scorr images
    if suffix == 'scorr':
        return ''
    
    thumb_type = suffix_map.get(suffix, suffix)
    
    try:
        return reverse('custom_code:decam_thumbnail', kwargs={
            'candidate_id': candidate.id,
            'thumb_type': thumb_type,
        })
    except Exception as e:
        logger.error(f'Error generating DECam thumbnail URL: {e}')
        return ''


@register.filter
def is_decam(candidate):
    """
    Check if a candidate is from DECam.
    
    Usage in template:
        {% if candidate|is_decam %}
            ... DECam specific display ...
        {% endif %}
    """
    return getattr(candidate, 'facility', 'CSS') == 'DECam'


@register.filter
def facility_name(candidate):
    """
    Returns human-readable facility name.
    
    Usage in template:
        {{ candidate|facility_name }}
    """
    facility = getattr(candidate, 'facility', 'CSS')
    names = {
        'CSS': 'Catalina Sky Survey',
        'DECam': 'Dark Energy Camera',
    }
    return names.get(facility, facility)
