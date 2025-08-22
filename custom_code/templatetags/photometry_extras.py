from django import template
from django.conf import settings
from guardian.shortcuts import get_objects_for_user
from plotly import offline
import plotly.graph_objs as go
from plotly import colors
from tom_dataproducts.models import ReducedDatum
import numpy as np
from datetime import datetime
import re
from matplotlib.colors import to_hex
from lightcurve_fitting.filters import filtdict

register = template.Library()

# any marker colors or shapes that we want to keep static across all pages
COLOR_MAP = {name: to_hex(fltr.color) for name, fltr in filtdict.items()}
MARKER_MAP = {
    'limit': 50,  # arrow-bar-down
    'ATLAS': 2,  # diamond
    'MARS': 1,  # square
    'SAGUARO pipeline': 0,  # circle
    'ZTF': 1,  # square
    'P48': 1,  # square
}

# other marker colors and shapes for sources not listed above
OTHER_MARKERS = list(range(33))  # all filled markers in Plotly
OTHER_MARKERS.remove(6)  # do not use triangle-down, too close to arrow-bar-down
OTHER_COLORS = colors.qualitative.Plotly  # default Plotly color sequence


def get_marker_for_photometry_point(label, marker_map, others):
    """
    Get marker properties (color or shape) from a dictionary `marker_map` after parsing the photometry `label`.
    If there is no matching label in the dictionary, pick the next item in `others`.
    """
    base_label = re.sub(' \(.*\)', '', re.sub('[-_].*', '', label))
    if label in marker_map:
        return marker_map[label]
    elif base_label in marker_map:
        return marker_map[base_label]
    else:
        for marker in others:
            if marker not in marker_map.values():
                marker_map[base_label] = marker
                print(marker_map)
                return marker


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
            phot_point = {'timestamp': datum.timestamp, 'magnitude': datum.value['magnitude']}
        elif 'limit' in datum.value.keys():
            phot_point = {'timestamp': datum.timestamp, 'limit': datum.value['limit']}
        else:
            continue

        if target.distance is not None:
            dm = 5. * (np.log10(target.distance) + 5.)
            phot_point['absmag'] = (phot_point.get('magnitude') or phot_point.get('limit')) - dm

        recent_det['data'].append(phot_point)

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
            filter_data.setdefault('error', []).append(datum.value.get('error', 0.))
        elif 'limit' in datum.value:
            limits.setdefault(datum.source_name, {})
            limits[datum.source_name].setdefault(datum.value['filter'], {})
            filter_data = limits[datum.source_name][datum.value['filter']]
            filter_data.setdefault('time', []).append(datum.timestamp)
            filter_data.setdefault('limit', []).append(datum.value['limit'])

    plot_data = []
    all_ydata = []
    color_map = COLOR_MAP.copy()
    marker_map = MARKER_MAP.copy()
    other_colors = OTHER_COLORS.copy()
    other_markers = OTHER_MARKERS.copy()
    for source_name, source_values in detections.items():
        marker_symbol = get_marker_for_photometry_point(source_name, marker_map, other_markers)
        for filter_name, filter_values in source_values.items():
            marker_color = get_marker_for_photometry_point(filter_name, color_map, other_colors)
            series = go.Scatter(
                x=filter_values['time'],
                y=filter_values['magnitude'],
                mode='markers',
                marker_color=marker_color,
                marker_symbol=marker_symbol,
                name=f'{source_name} {filter_name}',
                error_y=dict(
                    type='data',
                    array=filter_values['error'],
                    visible=True
                )
            )
            plot_data.append(series)
            mags = np.array(filter_values['magnitude'], float)  # converts None --> nan (as well as any strings)
            errs = np.array(filter_values['error'], float)
            errs[np.isnan(errs)] = 0.  # missing errors treated as zero
            all_ydata.append(mags + errs)
            all_ydata.append(mags - errs)
    for source_name, source_values in limits.items():
        for filter_name, filter_values in source_values.items():
            marker_color = get_marker_for_photometry_point(filter_name, color_map, other_colors)
            series = go.Scatter(
                x=filter_values['time'],
                y=filter_values['limit'],
                mode='markers',
                opacity=0.5,
                marker_color=marker_color,
                marker_symbol=MARKER_MAP['limit'],
                name=f'{source_name} {filter_name} limits',
            )
            plot_data.append(series)
            all_ydata.append(np.array(filter_values['limit'], float))

    # scale the y-axis manually so that we know the range ahead of time and can scale the secondary y-axis to match
    if all_ydata:
        all_ydata = np.concatenate(all_ydata)
        ymin = np.nanpercentile(all_ydata, 0.1)
        ymax = np.nanpercentile(all_ydata, 99.9)
        yrange = ymax - ymin
        ymin_view = ymin - 0.05 * yrange
        ymax_view = ymax + 0.05 * yrange
    else:
        ymin_view = 0.
        ymax_view = 0.
    yaxis = {
        'title': 'Apparent Magnitude',
        'range': (ymax_view, ymin_view),
        'showgrid': grid,
        'color': label_color,
        'showline': True,
        'linecolor': label_color,
        'mirror': True,
        'zeroline': False,
    }
    if target.distance is not None:
        dm = 5. * (np.log10(target.distance) + 5.)
        yaxis2 = {
            'title': 'Absolute Magnitude',
            'range': (ymax_view - dm, ymin_view - dm),
            'showgrid': False,
            'overlaying': 'y',
            'side': 'right',
            'zeroline': False,
        }
        plot_data.append(go.Scatter(x=[], y=[], yaxis='y2'))  # dummy data set for abs mag axis
    else:
        yaxis2 = None

    layout = go.Layout(
        xaxis={
            'showgrid': grid,
            'color': label_color,
            'showline': True,
            'linecolor': label_color,
            'mirror': True,
        },
        yaxis=yaxis,
        yaxis2=yaxis2,
        height=height,
        width=width,
        paper_bgcolor=background,
        plot_bgcolor=background,
        legend={
            'font_color': label_color,
            'xanchor': 'center',
            'yanchor': 'bottom',
            'x': 0.5,
            'y': 1.,
            'orientation': 'h',
        }
    )
    fig = go.Figure(data=plot_data, layout=layout)

    for candidate in target.eventcandidate_set.all():
        t0 = datetime.strptime(candidate.nonlocalizedevent.sequences.last().details['time'], '%Y-%m-%dT%H:%M:%S.%f%z')
        fig.add_vline(t0.timestamp() * 1000., annotation_text=candidate.nonlocalizedevent.event_id)

    return {
        'target': target,
        'plot': offline.plot(fig, output_type='div', show_link=False)
    }


@register.filter
def format_mag(datum, d=2):
    if datum.get('magnitude'):
        datum['magnitude'] = float(datum['magnitude'])
        if datum.get('error'):
            datum['error'] = float(datum['error'])
            display_str = f'{{magnitude:.{d}f}} ± {{error:.{d}f}}'
        elif datum.get('limit'):
            display_str = f'> {{magnitude:.{d}f}}'
        else:
            display_str = f'{{magnitude:.{d}f}}'
        return display_str.format(**datum)


@register.filter
def error_to_snr(error):
    return 2.5 / np.log(10.) / error
