"""
Page views for candidate vetting
"""
from urllib.parse import urlparse, parse_qs

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.base import RedirectView
from django.http import HttpResponseRedirect

from trove_targets.models import Target
from candidate_vetting.vet_bns import vet_bns
from candidate_vetting.vet_phot import find_public_phot
from candidate_vetting.public_catalogs.phot_catalogs import ZTF_Forced_Phot

import requests

class TargetVettingView(LoginRequiredMixin, RedirectView):
    """
    View that runs or reruns the kilonova candidate vetting code and stores the results
    """
    def get(self, request, *args, **kwargs):
        """
        Method that handles the GET requests for this view. Calls the kilonova vetting code.
        """        
        target = Target.objects.get(pk=kwargs['pk'])

        # get the nonlocalized event name from the referer
        query_params = parse_qs(
            urlparse(
                request.META.get("HTTP_REFERER")
            ).query
        )
        nonlocalized_event_name = query_params.get("nonlocalizedevent")
        if nonlocalized_event_name is not None:
            # because parse_qs returns lists for each query item
            nonlocalized_event_name = nonlocalized_event_name[0]


        # first check for new photometry
        messages.info(request, "Checking for new public forced photometry. We will vet without this, please consider running the vetting again in ~3-5 minutes.")
        find_public_phot(target, queue_priority=0) # set priority=0 so this jumps the queue (clearly a user cares about it)

        # then run the vetting
        vet_bns(target.id, nonlocalized_event_name)
        
        return HttpResponseRedirect(self.get_redirect_url())

    def get_redirect_url(self):
        """
        Returns redirect URL as specified in the HTTP_REFERER field of the request.

        :returns: referer
        :rtype: str
        """
        referer = self.request.META.get('HTTP_REFERER', '/')
        return referer

class TargetFPView(LoginRequiredMixin, RedirectView):
    """
    Class to run forced photometry for a target 
    """

    def get(self, request, *args, **kwargs):

        messages.info(request, "Checking for new public forced photometry. This can take ~minutes for ATLAS and ~hours-days for ZTF. We suggest you check back later.")
        
        target = Target.objects.get(id=kwargs['pk'])

        # check TNS and ATLAS
        find_public_phot(
            target=target,
            days_ago_max=365,
            queue_priority=0
        )

        # then also run ZTF forced photometry
        # this will only actually be ingested after the ZTF forced photometry runs
        ztf = ZTF_Forced_Phot()
        ztf.query(
            target=target,
            days_ago=365
        )
        
        return HttpResponseRedirect(self.get_redirect_url())

    def get_redirect_url(self):
        """
        Returns redirect URL as specified in the HTTP_REFERER field of the request.

        :returns: referer
        :rtype: str
        """
        referer = self.request.META.get('HTTP_REFERER', '/')
        return referer
