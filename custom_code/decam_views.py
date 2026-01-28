"""
Views for serving DECam thumbnails from the database.

CSS thumbnails are served from URLs (http://sassy.as.arizona.edu/...),
but DECam thumbnails are stored as binary PNG data in the database
and need to be served via these views.
"""

from django.http import HttpResponse, Http404
from django.views import View

from .models import Candidate, DecamCandidate


class DecamCandidateView(View):
    """
    Serve DECam thumbnail images from the database.
    
    URL pattern: /decam/thumbnail/<candidate_id>/<thumb_type>/
    
    Where thumb_type is one of: 'template', 'science', 'difference'
    
    Optional query parameter: 
        mjd - specific MJD to get thumbnail for (default: most recent)
    """
    
    def get(self, request, candidate_id, thumb_type):
        """
        Serve the thumbnail image as PNG.
        
        Parameters
        ----------
        candidate_id : int
            ID of the Candidate object
        thumb_type : str
            Type of thumbnail: 'template', 'science', or 'difference'
        """
        # Map thumb_type to database field name
        field_map = {
            'template': 'thumb_template',
            'science': 'thumb_science', 
            'difference': 'thumb_difference',
            # Aliases for compatibility
            'ref': 'thumb_template',
            'sci': 'thumb_science',
            'diff': 'thumb_difference',
        }
        
        if thumb_type not in field_map:
            raise Http404(f"Invalid thumbnail type: {thumb_type}")
        
        field_name = field_map[thumb_type]
        
        # Get the candidate
        try:
            candidate = Candidate.objects.get(id=candidate_id)
        except Candidate.DoesNotExist:
            raise Http404("Candidate not found")
        
        # Check for specific MJD in query params
        mjd = request.GET.get('mjd')
        
        if mjd:
            try:
                thumbnail = DecamCandidate.objects.filter(
                    candidate=candidate,
                    mjd_obs=float(mjd)
                ).first()
            except ValueError:
                raise Http404("Invalid MJD value")
        else:
            # Get the most recent thumbnail
            thumbnail = DecamCandidate.objects.filter(
                candidate=candidate
            ).order_by('-mjd_obs').first()
        
        if not thumbnail:
            raise Http404("Thumbnail not found")
        
        # Get the image data
        image_data = getattr(thumbnail, field_name, None)
        
        if not image_data:
            raise Http404(f"No {thumb_type} thumbnail available")
        
        # Return the image
        response = HttpResponse(image_data, content_type='image/png')
        response['Content-Disposition'] = f'inline; filename="{candidate_id}_{thumb_type}.png"'
        
        # Cache for 1 hour since thumbnails don't change
        response['Cache-Control'] = 'max-age=3600'
        
        return response
