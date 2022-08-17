from django import template
from django.conf import settings
from guardian.shortcuts import get_objects_for_user
from plotly import offline
import plotly.graph_objs as go
from tom_dataproducts.models import ReducedDatum

register = template.Library()

COLOR_MAP = {
    'g': 'green',
    'r': 'red',
    'i': 'darkred',
    'c': 'cyan',
    'o': 'orange',
}
MARKER_MAP = {
    'limit': 50,  # arrow-bar-down
    'ATLAS': 2,  # diamond
    'MARS': 1,  # square
    'SAGUARO pipeline': 0,  # circle
    'ZTF': 1,  # square
}


@register.inclusion_tag('tom_dataproducts/partials/recent_photometry.html', takes_context=True)
def recent_photometry(context, target, limit=1):
    """
    Displays a table of the most recent photometric points for a target.
    """

    if settings.TARGET_PERMISSIONS_ONLY:
        datums = ReducedDatum.objects.filter(target=target, data_type=settings.DATA_PRODUCT_TYPES['photometry'][0])
    else:
        datums = get_objects_for_user(context['request'].user,
                                      'tom_dataproducts.view_reduceddatum',
                                      klass=ReducedDatum.objects.filter(
                                        target=target,
                                        data_type=settings.DATA_PRODUCT_TYPES['photometry'][0]))
    recent_det = {'data': []}
    for datum in datums.order_by('-timestamp')[:limit]:
        if 'magnitude' in datum.value.keys():
            recent_det['data'].append({'timestamp': datum.timestamp, 'magnitude': datum.value['magnitude']})
        elif 'limit' in datum.value.keys():
            recent_det['data'].append({'timestamp': datum.timestamp, 'limit': datum.value['limit']})
        else:
            continue

    return recent_det


@register.inclusion_tag('tom_dataproducts/partials/photometry_for_target.html', takes_context=True)
def photometry_for_target(context, target, width=700, height=600, background=None, label_color=None, grid=True):
    """
    Renders a photometric plot for a target.

    This templatetag requires all ``ReducedDatum`` objects with a data_type of ``photometry`` to be structured with the
    following keys in the JSON representation: magnitude, error, filter

    :param width: Width of generated plot
    :type width: int

    :param height: Height of generated plot
    :type width: int

    :param background: Color of the background of generated plot. Can be rgba or hex string.
    :type background: str

    :param label_color: Color of labels/tick labels. Can be rgba or hex string.
    :type label_color: str

    :param grid: Whether to show grid lines.
    :type grid: bool
    """
    if settings.TARGET_PERMISSIONS_ONLY:
        datums = ReducedDatum.objects.filter(target=target, data_type=settings.DATA_PRODUCT_TYPES['photometry'][0])
    else:
        datums = get_objects_for_user(context['request'].user,
                                      'tom_dataproducts.view_reduceddatum',
                                      klass=ReducedDatum.objects.filter(
                                        target=target,
                                        data_type=settings.DATA_PRODUCT_TYPES['photometry'][0]))

    detections = {}
    limits = {}
    for datum in datums:
        if 'magnitude' in datum.value:
            detections.setdefault(datum.source_name, {})
            detections[datum.source_name].setdefault(datum.value['filter'], {})
            filter_data = detections[datum.source_name][datum.value['filter']]
            filter_data.setdefault('time', []).append(datum.timestamp)
            filter_data.setdefault('magnitude', []).append(datum.value['magnitude'])
            filter_data.setdefault('error', []).append(datum.value.get('error'))
        elif 'limit' in datum.value:
            limits.setdefault(datum.source_name, {})
            limits[datum.source_name].setdefault(datum.value['filter'], {})
            filter_data = limits[datum.source_name][datum.value['filter']]
            filter_data.setdefault('time', []).append(datum.timestamp)
            filter_data.setdefault('limit', []).append(datum.value['limit'])

    plot_data = []
    for source_name, source_values in detections.items():
        for filter_name, filter_values in source_values.items():
            series = go.Scatter(
                x=filter_values['time'],
                y=filter_values['magnitude'],
                mode='markers',
                marker=dict(color=COLOR_MAP.get(filter_name)),
                marker_symbol=MARKER_MAP.get(source_name),
                name=f'{source_name} {filter_name}',
                error_y=dict(
                    type='data',
                    array=filter_values['error'],
                    visible=True
                )
            )
            plot_data.append(series)
    for source_name, source_values in limits.items():
        for filter_name, filter_values in source_values.items():
            series = go.Scatter(
                x=filter_values['time'],
                y=filter_values['limit'],
                mode='markers',
                opacity=0.5,
                marker=dict(color=COLOR_MAP.get(filter_name)),
                marker_symbol=MARKER_MAP['limit'],
                name=f'{source_name} {filter_name} limits',
            )
            plot_data.append(series)

    layout = go.Layout(
        yaxis=dict(autorange='reversed'),
        height=height,
        width=width,
        paper_bgcolor=background,
        plot_bgcolor=background

    )
    layout.legend.font.color = label_color
    fig = go.Figure(data=plot_data, layout=layout)
    fig.update_yaxes(showgrid=grid, color=label_color, showline=True, linecolor=label_color, mirror=True)
    fig.update_xaxes(showgrid=grid, color=label_color, showline=True, linecolor=label_color, mirror=True)
    return {
        'target': target,
        'plot': offline.plot(fig, output_type='div', show_link=False)
    }