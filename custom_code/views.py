import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect, StreamingHttpResponse
from django.views.generic.base import RedirectView
from django.views.generic.edit import CreateView, TemplateResponseMixin, FormMixin, ProcessFormView, UpdateView
from django_filters.views import FilterView
from django.shortcuts import redirect
from guardian.mixins import PermissionListMixin
from guardian.shortcuts import get_objects_for_user

from tom_targets.models import Target, TargetList
from tom_targets.views import TargetNameSearchView as OldTargetNameSearchView, TargetListView as OldTargetListView
from tom_observations.views import ObservationCreateView as OldObservationCreateView
from tom_dataproducts.models import ReducedDatum
from tom_nonlocalizedevents.models import NonLocalizedEvent, EventLocalization, EventCandidate
from tom_surveys.models import SurveyObservationRecord
from tom_treasuremap.reporting import report_to_treasure_map
from .models import Candidate, SurveyFieldCredibleRegion, Profile
from .filters import CandidateFilter, CSSFieldCredibleRegionFilter, NonLocalizedEventFilter
from .forms import TargetListExtraFormset, ProfileUpdateForm, NonLocalizedEventFormHelper, CandidateFormHelper
from .hooks import target_post_save, update_or_create_target_extra

import json
import requests
import time
from io import StringIO

from kne_cand_vetting.survey_phot import ATLAS_forcedphot
import numpy as np
from astropy.time import Time, TimezoneInfo
import paramiko
import os

DB_CONNECT = "postgresql+psycopg2://{USER}:{PASSWORD}@{HOST}:{PORT}/{NAME}".format(**settings.DATABASES['default'])

logger = logging.getLogger(__name__)


class TargetGroupingCreateView(LoginRequiredMixin, CreateView):
    """
    View that handles the creation of ``TargetList`` objects, also known as target groups. Requires authentication.
    """
    model = TargetList
    fields = ['name']
    success_url = reverse_lazy('targets:targetgrouping')
    template_name = 'tom_targets/targetlist_form.html'

    def form_valid(self, form):
        """
        Runs after form validation. Creates the ``TargetList``, and creates any ``TargetListExtra`` objects,
        then redirects to the success URL.

        :param form: Form data for target creation
        :type form: subclass of TargetCreateForm
        """
        super().form_valid(form)
        extra = TargetListExtraFormset(self.request.POST)
        if extra.is_valid():
            extra.instance = self.object
            extra.save()
        else:
            form.add_error(None, extra.errors)
            form.add_error(None, extra.non_form_errors())
            return super().form_invalid(form)
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        """
        Inserts certain form data into the context dict.

        :returns: Dictionary with the following keys:

                  `type_choices`: ``tuple``: Tuple of 2-tuples of strings containing available target types in the TOM

                  `extra_form`: ``FormSet``: Django formset with fields for arbitrary key/value pairs
        :rtype: dict
        """
        context = super(TargetGroupingCreateView, self).get_context_data(**kwargs)
        context['extra_form'] = TargetListExtraFormset()
        return context


class CandidateListView(FilterView):
    """
    View for listing candidates in the TOM.
    """
    template_name = 'tom_targets/candidate_list.html'
    paginate_by = 100
    strict = False
    model = Candidate
    filterset_class = CandidateFilter
    formhelper_class = CandidateFormHelper

    def get_filterset(self, filterset_class):
        kwargs = self.get_filterset_kwargs(filterset_class)
        filterset = filterset_class(**kwargs)
        filterset.form.helper = self.formhelper_class()
        return filterset

    def get_queryset(self):
        """
        Gets the set of ``Candidate`` objects associated with ``Target`` objects that the user has permission to view.

        :returns: Set of ``Candidate`` objects
        :rtype: QuerySet
        """
        return super().get_queryset().filter(
            target__in=get_objects_for_user(self.request.user, 'tom_targets.view_target')
        )


class ObservationCreateView(OldObservationCreateView):
    """
    Modify the built-in ObservationCreateView to populate any "magnitude" field with the latest observed magnitude
    """
    template_name = 'tom_observations/observation_form.html'

    def get_initial(self):
        initial = super().get_initial()
        target = self.get_target()
        photometry = target.reduceddatum_set.filter(data_type='photometry')
        if photometry.exists():
            latest_photometry = photometry.latest().value
            if 'magnitude' in latest_photometry:
                initial['magnitude'] = latest_photometry['magnitude']
            elif 'limit' in latest_photometry:
                initial['magnitude'] = latest_photometry['limit']
        return initial


class TargetVettingView(LoginRequiredMixin, RedirectView):
    """
    View that runs or reruns the kilonova candidate vetting code and stores the results
    """
    def get(self, request, *args, **kwargs):
        """
        Method that handles the GET requests for this view. Calls the kilonova vetting code.
        """
        target = Target.objects.get(pk=kwargs['pk'])
        banners = target_post_save(target, created=True)
        for banner in banners:
            messages.success(request, banner)
        return HttpResponseRedirect(self.get_redirect_url())

    def get_redirect_url(self):
        """
        Returns redirect URL as specified in the HTTP_REFERER field of the request.

        :returns: referer
        :rtype: str
        """
        referer = self.request.META.get('HTTP_REFERER', '/')
        return referer


class TargetATLASForcedPhot(LoginRequiredMixin, RedirectView):
    """
    View that runs ATLAS forced photometry over past 200 days and stores result.
    """
    def get(self, request, *args, **kwargs):
        """
        Method that handles the GET requests for this view. Calls the ATLAS forced photometry function.
        Converts micro-Jansky values to AB magnitude and separates detections and non-detections.
        """
        target = Target.objects.get(pk=kwargs['pk'])
        atlasphot = ATLAS_forcedphot(target.ra, target.dec, token=settings.ATLAS_API_KEY)

        if len(atlasphot)>1:
            for candidate in atlasphot:
                if candidate['uJy'] >= 5*candidate['duJy']:
                    nondetection = False
                elif candidate['uJy'] < 5*candidate['duJy']:
                    nondetection = True
                else:
                    continue
                mjd = Time(candidate['mjd'], format='mjd', scale='utc')
                mjd.to_datetime(timezone=TimezoneInfo())
                value = {
                    'filter': candidate['F']
                }
                if nondetection:
                    value['limit'] = candidate['mag5sig']
                else:
                    value['magnitude'] = -2.5*np.log10(candidate['uJy'] * 1e-29) - 48.6
                    value['error'] = 1.09 * candidate['duJy'] / candidate['uJy']
                rd, _ = ReducedDatum.objects.get_or_create(
                    timestamp=mjd.to_datetime(timezone=TimezoneInfo()),
                    value=value,
                    source_name='ATLAS',
                    data_type='photometry',
                    target=target)

        return HttpResponseRedirect(self.get_redirect_url())

    def get_redirect_url(self):
        """
        Returns redirect URL as specified in the HTTP_REFERER field of the request.

        :returns: referer
        :rtype: str
        """
        referer = self.request.META.get('HTTP_REFERER', '/')
        return referer


class TargetNameSearchView(OldTargetNameSearchView):
    """
    View for searching by target name. If the search returns one result, the view redirects to the corresponding
    TargetDetailView. Otherwise, the view redirects to the TargetListView.
    """

    def get(self, request, *args, **kwargs):
        self.kwargs['name'] = request.GET.get('name').strip()
        return super().get(request, *args, **kwargs)


class TargetListView(OldTargetListView):
    """
    View for listing targets in the TOM. Only shows targets that the user is authorized to view. Requires authorization.

    Identical to the built-in TargetListView but does not display unconfirmed candidates (names starting with "J")
    """
    def get_queryset(self):
        return super().get_queryset().exclude(name__startswith='J')


class CSSFieldListView(FilterView):
    """
    View for listing candidates in the TOM.
    """
    template_name = 'tom_nonlocalizedevents/cssfield_list.html'
    paginate_by = 100
    strict = False
    model = SurveyFieldCredibleRegion
    filterset_class = CSSFieldCredibleRegionFilter

    def get_eventlocalization(self):
        if 'localization_id' in self.kwargs:
            return EventLocalization.objects.get(id=self.kwargs['localization_id'])
        elif 'event_id' in self.kwargs:
            nle = NonLocalizedEvent.objects.get(event_id=self.kwargs['event_id'])
            seq = nle.sequences.last()
            if seq is not None:
                return seq.localization

    def get_nonlocalizedevent(self):
        if 'localization_id' in self.kwargs:
            localization = EventLocalization.objects.get(id=self.kwargs['localization_id'])
            return localization.nonlocalizedevent
        elif 'event_id' in self.kwargs:
            return NonLocalizedEvent.objects.get(event_id=self.kwargs['event_id'])

    def get_queryset(self):
        queryset = super().get_queryset()
        localization = self.get_eventlocalization()
        if localization is None:
            return queryset.none()
        else:
            return queryset.filter(localization=localization)

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(object_list=object_list, **kwargs)
        context['nonlocalizedevent'] = self.get_nonlocalizedevent()
        context['eventlocalization'] = self.get_eventlocalization()
        return context


def generate_prog_file(css_credible_regions):
    return ','.join([cr.survey_field.name for cr in css_credible_regions]) + '\n'


def submit_to_css(css_credible_regions, event_id, request=None):
    filenames = []
    try:
        with paramiko.SSHClient() as ssh:
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(settings.CSS_HOSTNAME, username=settings.CSS_USERNAME,
                        disabled_algorithms={'pubkeys': ['rsa-sha2-256', 'rsa-sha2-512']})
            # See https://www.paramiko.org/changelog.html#2.9.0 for why disabled_algorithms is required
            sftp = ssh.open_sftp()
            for i, group in enumerate(css_credible_regions):
                filename = f'Saguaro_{event_id}_{i + 1:d}.prog'
                filenames.append(filename)
                with sftp.open(os.path.join(settings.CSS_DIRNAME, filename), 'w') as f:
                    f.write(generate_prog_file(group))
                banner = f'Submitted {filename} to CSS'
                logger.info(banner)
                if request is not None:
                    messages.success(request, banner)
    except Exception as e:
        logger.error(str(e))
        if request is not None:
            messages.error(request, str(e))
    return filenames


def create_observation_records(credible_regions, observation_id, user, facility, parameters=None):
    records = []
    for group, oid in zip(credible_regions, observation_id):
        for cr in group:
            record = SurveyObservationRecord.objects.create(
                survey_field=cr.survey_field,
                user=user,
                facility=facility,
                parameters=parameters or {},
                observation_id=oid,
                status='PENDING',
                scheduled_start=cr.scheduled_start,
            )
            cr.observation_record = record
            cr.save()
            records.append(record)
    return records


class CSSFieldExportView(CSSFieldListView):
    """
    View that handles the export of CSS Fields to .prog file(s).
    """
    def post(self, request, *args, **kwargs):
        css_credible_regions = self.get_selected_fields(request)
        text = ''.join([generate_prog_file(group) for group in css_credible_regions])
        return self.render_to_response(text)

    def get_selected_fields(self, request):
        target_ids = None if request.POST.get('isSelectAll') == 'True' else request.POST.getlist('selected-target')
        localization = self.get_eventlocalization()
        credible_regions = localization.surveyfieldcredibleregions.filter(group__isnull=False)
        if target_ids is not None:
            credible_regions = credible_regions.filter(id__in=target_ids)
        group_numbers = list(credible_regions.order_by('group').values_list('group', flat=True).distinct())
        # evaluate this as a list now to maintain the order
        groups = [list(credible_regions.filter(group=g).order_by('rank_in_group')) for g in group_numbers]
        return groups

    def render_to_response(self, text, **response_kwargs):
        """
        Returns a response containing the exported .prog file(s) of selected fields.

        :returns: response class with ASCII
        :rtype: StreamingHttpResponse
        """
        file_buffer = StringIO(text)
        file_buffer.seek(0)  # goto the beginning of the buffer
        response = StreamingHttpResponse(file_buffer, content_type="text/ascii")
        nle = self.get_nonlocalizedevent()
        filename = f"Saguaro_{nle.event_id}.prog"
        response['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)
        return response


class CSSFieldSubmitView(LoginRequiredMixin, RedirectView, CSSFieldExportView):
    """
    View that handles the submission of CSS Fields to CSS and reporting to the GW Treasure Map.
    """
    def post(self, request, *args, **kwargs):
        """
        Method that handles the POST requests for this view.
        """
        css_credible_regions = self.get_selected_fields(request)
        nle = self.get_nonlocalizedevent()
        filenames = submit_to_css(css_credible_regions, nle.event_id, request=request)
        params = {'pos_angle': 0., 'depth': 20.5, 'depth_unit': 'ab_mag', 'band': 'open'}
        records = create_observation_records(css_credible_regions, filenames, request.user, 'CSS', params)
        response = report_to_treasure_map(records, nle)
        for message in response['SUCCESSES']:
            messages.success(request, message)
        for message in response['WARNINGS']:
            messages.warning(request, message)
        for message in response['ERRORS']:
            messages.error(request, message)
        return HttpResponseRedirect(self.get_redirect_url())

    def get_redirect_url(self):
        """
        Returns redirect URL as specified in the HTTP_REFERER field of the request.

        :returns: referer
        :rtype: str
        """
        referer = self.request.META.get('HTTP_REFERER', '/')
        return referer


class NonLocalizedEventListView(FilterView):
    """
    Unadorned Django ListView subclass for NonLocalizedEvent model.
    """
    model = NonLocalizedEvent
    template_name = 'tom_nonlocalizedevents/nonlocalizedevent_list.html'
    filterset_class = NonLocalizedEventFilter
    paginate_by = 100
    formhelper_class = NonLocalizedEventFormHelper

    def get_filterset(self, filterset_class):
        kwargs = self.get_filterset_kwargs(filterset_class)
        filterset = filterset_class(**kwargs)
        filterset.form.helper = self.formhelper_class()
        return filterset

    def get_queryset(self):
        # '-created' is most recent first
        qs = NonLocalizedEvent.objects.order_by('-created')
        return qs


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = Profile
    template_name = 'tom_common/update_user_profile.html'
    form_class = ProfileUpdateForm

    def get_success_url(self):
        """
        Returns the redirect URL for a successful update. If the current user is a superuser, returns the URL for the
        user list. Otherwise, returns the URL for updating the current user.

        :returns: URL for user list or update user
        :rtype: str
        """
        return reverse_lazy('custom_code:profile-update', kwargs={'pk': self.get_object().id})


class EventCandidateCreateView(LoginRequiredMixin, RedirectView):
    """
    View that handles the association of a target with a NonLocalizedEvent on a button press
    """
    def get(self, request, *args, **kwargs):
        """
        Method that handles the GET requests for this view.
        """
        nonlocalizedevent = NonLocalizedEvent.objects.get(event_id=self.kwargs['event_id'])
        target = Target.objects.get(id=self.kwargs['target_id'])
        viability_reason = f'added from candidates list by {self.request.user.first_name}'
        EventCandidate.objects.create(nonlocalizedevent=nonlocalizedevent, target=target,
                                      viability_reason=viability_reason)
        return HttpResponseRedirect(self.get_redirect_url())

    def get_redirect_url(self):
        """
        Returns redirect URL as specified in the HTTP_REFERER field of the request.

        :returns: referer
        :rtype: str
        """
        referer = self.request.META.get('HTTP_REFERER', '/')
        return referer
