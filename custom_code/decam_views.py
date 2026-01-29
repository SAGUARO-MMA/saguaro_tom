"""
Views for serving DECam thumbnails from the database.

CSS thumbnails are served from URLs (http://sassy.as.arizona.edu/...),
but DECam thumbnails are stored as binary PNG data in the database
and need to be served via these views.
"""

from django.http import HttpResponse, Http404
from django.views import View
from django.views.generic import ListView 
from astropy.time import Time
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
            ID of the DecamCandidate object
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
        
        # Get the DecamCandidate directly by its ID
        try:
            decam_candidate = DecamCandidate.objects.get(id=candidate_id)
        except DecamCandidate.DoesNotExist:
            raise Http404("DECam candidate not found")
        
        # Get the image data
        image_data = getattr(decam_candidate, field_name, None)
        
        if not image_data:
            raise Http404(f"No {thumb_type} thumbnail available")
        
        # Return the image
        response = HttpResponse(image_data, content_type='image/png')
        response['Content-Disposition'] = f'inline; filename="decam_{candidate_id}_{thumb_type}.png"'
        
        # Cache for 1 hour since thumbnails don't change
        response['Cache-Control'] = 'max-age=3600'
        
        return response


class DecamCandidateListView(ListView):
    """
    View for listing DECam candidates with filtering.
    Groups observations by target and date.
    """
    model = DecamCandidate
    template_name = 'tom_targets/decam_candidate_list.html'
    context_object_name = 'decam_candidates'
    paginate_by = 50  # Fewer since we're grouping
    
    def get_queryset(self):
        """Apply filters and return candidates."""
        from django.db.models import Q
        
        queryset = DecamCandidate.objects.select_related(
            'target', 
            'observation_record',
            'observation_record__survey_field'
        ).all()
        
        # Apply all the filters (keep existing filter logic)
        obs_date = self.request.GET.get('date')
        if obs_date:
            try:
                t = Time(obs_date, format='iso')
                mjd_start = t.mjd
                mjd_end = mjd_start + 1.0
                queryset = queryset.filter(mjd_obs__gte=mjd_start, mjd_obs__lt=mjd_end)
            except:
                pass
        
        field = self.request.GET.get('field')
        if field and field != 'all':
            queryset = queryset.filter(observation_record__survey_field__name=field)
        
        filter_band = self.request.GET.get('filter_band')
        if filter_band and filter_band != 'all':
            queryset = queryset.filter(filter_name=filter_band)
        
        cnn_min = self.request.GET.get('cnn_min')
        if cnn_min:
            try:
                queryset = queryset.filter(cnnscore__gte=float(cnn_min))
            except:
                pass
        
        snr_min = self.request.GET.get('snr_min')
        if snr_min:
            try:
                queryset = queryset.filter(snr_fphot__gte=float(snr_min))
            except:
                pass
        
        if self.request.GET.get('not_in_gaia') == 'true':
            queryset = queryset.filter(Q(in_gaia__isnull=True) | Q(in_gaia=''))
        
        if self.request.GET.get('has_host') == 'true':
            queryset = queryset.filter(Q(desi_bgs__isnull=False) & ~Q(desi_bgs=''))
        
        return queryset.order_by('target_id','-mjd_obs','filter_name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Group candidates by target and observation date
        from collections import defaultdict
        grouped = defaultdict(lambda: defaultdict(list))
        
        for candidate in self.get_queryset():
            if candidate.target and candidate.observation_date:
                # Group by target_id and date
                key = (candidate.target.id, candidate.observation_date)
                grouped[key]['target'] = candidate.target
                grouped[key]['date'] = candidate.observation_date
                grouped[key]['field'] = candidate.observation_record.survey_field.name if candidate.observation_record and candidate.observation_record.survey_field else '—'
                grouped[key]['observations'].append(candidate)
        
        # Convert to list and sort
        grouped_list = []
        for (target_id, date), data in grouped.items():
            # Organize observations by filter
            by_filter = {}
            for obs in data['observations']:
                if obs.filter_name:
                    by_filter[obs.filter_name] = obs
            
            grouped_list.append({
                'target': data['target'],
                'date': date,
                'field': data['field'],
                'by_filter': by_filter,
                'all_obs': data['observations'],
            })
        
        # Sort by date descending
        grouped_list.sort(key=lambda x: x['date'], reverse=True)
        
        context['grouped_candidates'] = grouped_list
        
        # Keep existing context for filters
        all_candidates = DecamCandidate.objects.all()
        
        dates_dict = {}
        for candidate in all_candidates.filter(mjd_obs__isnull=False):
            if candidate.mjd_obs:
                try:
                    t = Time(candidate.mjd_obs, format='mjd')
                    obs_date = t.datetime.strftime('%Y-%m-%d')
                    dates_dict[obs_date] = dates_dict.get(obs_date, 0) + 1
                except:
                    continue
        
        context['observation_dates'] = sorted(dates_dict.items(), key=lambda x: x[0], reverse=True)
        
        fields = DecamCandidate.objects.filter(
            observation_record__survey_field__isnull=False
        ).values_list(
            'observation_record__survey_field__name', flat=True
        ).distinct().order_by('observation_record__survey_field__name')
        context['fields'] = list(fields)
        
        context['selected_date'] = self.request.GET.get('date', '')
        context['selected_field'] = self.request.GET.get('field', 'all')
        context['selected_filter_band'] = self.request.GET.get('filter_band', 'all')
        context['cnn_min'] = self.request.GET.get('cnn_min', '')
        context['snr_min'] = self.request.GET.get('snr_min', '')
        context['not_in_gaia'] = self.request.GET.get('not_in_gaia', 'false')
        context['has_host'] = self.request.GET.get('has_host', 'false')
        
        context['total_candidates'] = all_candidates.count()
        context['filtered_count'] = self.get_queryset().count()
        
        return context
