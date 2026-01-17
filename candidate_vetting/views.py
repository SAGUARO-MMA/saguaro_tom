"""
Page views for candidate vetting
"""
from urllib.parse import urlparse, parse_qs

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.base import RedirectView
from django.views.generic.edit import FormView
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect

from trove_targets.models import Target
from .forms import VettingChoiceForm 
from candidate_vetting.vet_bns import vet_bns
from candidate_vetting.vet_phot import find_public_phot

import requests

class TargetVettingFormView(FormView):
    template_name = "candidate_vetting/vetting_form.html"
    form_class = VettingChoiceForm

    # TODO: Only give the user the form if there is a non-localized event associated
    #       with this target. If there isn't, this should just redirect to the basic
    #       target vetting!
    
    def form_valid(self, form):
        pk = self.kwargs["pk"]
        vetting_mode = form.cleaned_data["picked"]
        
        # (optional) do something with the form data here
        # e.g. save choices to session, database, etc.
        
        return redirect(
            "candidate_vetting:vet",
            pk=pk,
            vetting_mode=vetting_mode,
        )
        
    
class TargetVettingView(LoginRequiredMixin, RedirectView):
    """
    View that runs or reruns the kilonova candidate vetting code and stores the results
    """
    def get(self, request, *args, **kwargs):
        """
        Method that handles the GET requests for this view. Calls the kilonova vetting code.
        """        
        target = Target.objects.get(pk=kwargs['pk'])
        vetting_mode = kwargs.get("vetting_mode", "basic")

        # TODO: Based off the vetting_mode, set the vetting that is run. For example,
        #       if the user selects classical KN then we should run vet_bns
        
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
