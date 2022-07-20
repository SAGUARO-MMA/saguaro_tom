import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView, TemplateResponseMixin, FormMixin, ProcessFormView
from django_filters.views import FilterView
from django.shortcuts import redirect
from guardian.mixins import PermissionListMixin

from tom_targets.models import Target, TargetList
from custom_code.models import Candidate
from custom_code.filters import CandidateFilter
from .forms import TargetListExtraFormset, TargetReportForm, TNS_FILTER_CHOICES, TNS_INSTRUMENT_CHOICES

import json
import requests
from saguaro_tom import settings
import time
# from tom_catalogs.harvesters.tns import TNS_URL
TNS_URL = 'https://sandbox.wis-tns.org/api'  # TODO: change this to the main site
TNS = settings.BROKERS['TNS']  # includes the API credentials
TNS_MARKER = 'tns_marker' + json.dumps({'tns_id': TNS['bot_id'], 'type': 'bot', 'name': TNS['bot_name']})
TNS_FILTER_IDS = {name: fid for fid, name in TNS_FILTER_CHOICES}
TNS_INSTRUMENT_IDS = {name: iid for iid, name in TNS_INSTRUMENT_CHOICES}

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


class CandidateListView(PermissionListMixin, FilterView):
    """
    View for listing candidates in the TOM.
    """
    template_name = 'tom_targets/candidate_list.html'
    paginate_by = 25
    strict = False
    model = Candidate
    filterset_class = CandidateFilter


def send_tns_report(data):
    """
    Send a JSON bulk report to the Transient Name Server according to this manual:
    https://sandbox.wis-tns.org/sites/default/files/api/TNS_bulk_reports_manual.pdf
    """
    json_data = {'api_key': TNS['api_key'], 'data': data}
    response = requests.post(TNS_URL + '/bulk-report', headers={'User-Agent': TNS_MARKER}, data=json_data)
    response.raise_for_status()
    report_id = response.json()['data']['report_id']
    logger.info(f'Sent TNS report ID {report_id:d}')
    return report_id


def get_tns_report_reply(report_id):
    """
    Get feedback from the Transient Name Server in response to a bulk report according to this manual:
    https://sandbox.wis-tns.org/sites/default/files/api/TNS_bulk_reports_manual.pdf
    """
    json_data = {'api_key': TNS['api_key'], 'report_id': report_id}
    for _ in range(6):
        time.sleep(5)
        response = requests.post(TNS_URL + '/bulk-report-reply', headers={'User-Agent': TNS_MARKER}, data=json_data)
        if response.ok:
            break
    response.raise_for_status()
    feedback = response.json()['data']['feedback']['at_report'][0]
    if '100' in feedback:  # transient object was inserted
        iau_name = 'AT' + feedback['100']['objname']
        logger.info(f'New transient {iau_name} was created')
    elif '101' in feedback:  # transient object exists
        iau_name = feedback['101']['prefix'] + feedback['101']['objname']
        logger.info(f'Existing transient {iau_name} was reported')
    else:  # this should never happen
        iau_name = None
        logger.warning('Problem getting response from TNS')
    return iau_name


class TargetReportView(PermissionListMixin, TemplateResponseMixin, FormMixin, ProcessFormView):
    """
    View that handles reporting a target to the TNS.
    """
    form_class = TargetReportForm
    template_name = 'tom_targets/targetreport_form.html'

    def get_initial(self):
        target = Target.objects.get(pk=self.kwargs['pk'])
        initial = {
            'ra': target.ra,
            'dec': target.dec,
            'reporter': f'{self.request.user.get_full_name()}, on behalf of SAGUARO',
        }
        if target.reduceddatum_set.exists():
            reduced_datum = target.reduceddatum_set.latest()
            initial['obsdate'] = reduced_datum.timestamp
            initial['flux'] = reduced_datum.value['magnitude']
            initial['flux_error'] = reduced_datum.value['error']
            filter_name = reduced_datum.value.get('filter')
            if filter_name in TNS_FILTER_IDS:
                initial['filter_value'] = (TNS_FILTER_IDS[filter_name], filter_name)
            instrument_name = reduced_datum.value.get('instrument')
            if instrument_name in TNS_INSTRUMENT_IDS:
                initial['instrument_value'] = (TNS_INSTRUMENT_IDS[instrument_name], instrument_name)
        return initial

    def form_valid(self, form):
        report_id = send_tns_report(form.generate_tns_report())
        iau_name = get_tns_report_reply(report_id)

        # update the target name
        if iau_name is not None:
            target = Target.objects.get(pk=self.kwargs['pk'])
            target.name = iau_name
            target.save()
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse_lazy('targets:detail', kwargs=self.kwargs)
