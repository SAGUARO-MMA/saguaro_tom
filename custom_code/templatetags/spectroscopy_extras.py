import logging

from django import template
from django.conf import settings
from datetime import datetime
from guardian.shortcuts import get_objects_for_user
from plotly import offline
import plotly.graph_objs as go

from tom_dataproducts.forms import DataShareForm
from tom_dataproducts.models import SpectroscopyReducedDatum

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

register = template.Library()


# copied from tom_base except for datum.source_name was added to the "name" of each data series
@register.inclusion_tag('tom_dataproducts/partials/spectroscopy_for_target.html', takes_context=True)
def spectroscopy_for_target(context, target, dataproduct=None):
    """
    Renders a spectroscopic plot for a ``Target``. If a ``DataProduct`` is specified, it will only render a plot with
    that spectrum.
    """

    plot_data = []
    if settings.TARGET_PERMISSIONS_ONLY:
        datums = SpectroscopyReducedDatum.objects.filter(target=target)
    else:
        datums = get_objects_for_user(context['request'].user,
                                      'tom_dataproducts.view_spectroscopyreduceddatum',
                                      klass=SpectroscopyReducedDatum.objects.filter(target=target))
    if dataproduct:
        datums = datums.filter(data_product=dataproduct)

    for datum in datums.order_by('timestamp'):
        plot_data.append(go.Scatter(
            x=datum.wavelength,
            y=datum.flux,
            name=f"{datetime.strftime(datum.timestamp, '%Y-%m-%d')} {datum.source_name}"
        ))

    layout = go.Layout(
        height=600,
        width=700,
        xaxis=dict(
            tickformat="d"
        ),
        yaxis=dict(
            tickformat=".1g"
        )
    )
    return {
        'target': target,
        'plot': offline.plot(go.Figure(data=plot_data, layout=layout), output_type='div', show_link=False)
    }


# mostly copied from dataproduct_list_for_target in tom_base, but switched to SpectroscopyReducedDatum
@register.inclusion_tag('tom_dataproducts/partials/spectroscopy_datalist_for_target.html', takes_context=True)
def get_spectroscopy_data(context, target):
    """
    Given a ``Target``, returns a list of ``DataProduct`` objects associated with that ``Target``
    """
    if settings.TARGET_PERMISSIONS_ONLY:
        spectroscopy_for_user = target.spectroscopyreduceddatum_set.all()
    else:
        spectroscopy_for_user = get_objects_for_user(context['request'].user,
                                                     'tom_dataproducts.view_spectroscopyreduceddatum',
                                                     klass=target.spectroscopyreduceddatum_set.all())

    initial = {'submitter': context['request'].user,
               'target': target,
               'share_title': f"Updated data for {target.name}."}
    form = DataShareForm(initial=initial)

    return {
        'datums': spectroscopy_for_user.order_by('timestamp'),
        'target': target,
        'sharing_destinations': form.fields['share_destination'].choices,
        'data_product_share_form': form
    }
