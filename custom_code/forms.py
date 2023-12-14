from django import forms
from django.forms import inlineformset_factory
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, HTML
from crispy_forms.bootstrap import AppendedText, PrependedAppendedText
from tom_targets.models import TargetList
from .models import TargetListExtra, Profile
from datetime import datetime
import json
import os


TargetListExtraFormset = inlineformset_factory(TargetList, TargetListExtra, fields=('key', 'value'),
                                               widgets={'value': forms.TextInput()})


class ProfileUpdateForm(forms.ModelForm):
    """
    Form used for updating user profiles.
    """
    class Meta:
        model = Profile
        exclude = ('user',)
        labels = {
            'bbh_alerts': 'BBH alerts (HasNS < 1%)',
            'ns_alerts': 'NS alerts (HasNS > 1%)',
        }


class NonLocalizedEventFormHelper(FormHelper):
    layout = Layout(
            Row(
                Column('prefix'),
                Column('state'),
                Column(PrependedAppendedText('inv_far_min', '>', 'yr')),
                # Column('classification'),
                Column(PrependedAppendedText('distance_max', '<', 'Mpc')),
                Column(PrependedAppendedText('has_ns_min', '>', '%')),
                Column(PrependedAppendedText('has_remnant_min', '>', '%')),
            ),
            Row(
                Column(
                    Submit('submit', 'Filter'),
                    HTML('<a href="{% url \'custom_code:nonlocalizedevents\' %}" class="btn btn-secondary" title="Reset">Reset</a>'),
                    css_class='text-right',
                )
            )
        )


class CandidateFormHelper(FormHelper):
    layout = Layout(
        Row(
            Column('obsdate_range'),
            Column('mag_range'),
            Column('snr_range'),
            Column('mlscore_range'),
            Column('mlscore_real_range'),
            Column('mlscore_bogus_range'),
        ),
        Row(
            Column('cone_search'),
            Column('observation_record__survey_field'),
            Column('classification'),
            Column('localization'),
            Column('order', css_class='col-md-4'),
        ),
        Row(
            Column(
                Submit('submit', 'Filter'),
                HTML('<a href="{% url \'custom_code:candidates\' %}" class="btn btn-secondary" title="Reset">Reset</a>'),
                css_class='text-right',
            )
        )
    )
