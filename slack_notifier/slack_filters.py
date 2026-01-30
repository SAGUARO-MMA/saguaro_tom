"""
Custom filters (i.e., subclasses of SlackNotifier)
"""
import json
from datetime import datetime
import numpy as np

from .slack_notifier import SlackNotifier
from custom_code.templatetags.target_extras import split_name
from django.conf import settings

ALERT_LINKS = ' '.join([f'<{link}|{service}>' for link, service in settings.TARGET_LINKS])

class LSST_DDF_SlackFilter(SlackNotifier):

    def __init__(self, token=settings.SLACK_TOKEN_TNS):
        super().__init__(
            slack_channel = "alerts",
            token = token
        )

    def filter_alert_stream(self, target):
        pass

class DistanceLimitedSlackFilter(SlackNotifier):

    def __init__(self, max_dist, token=settings.SLACK_TOKEN_TNS):
        self.max_dist = max_dist
        super().__init__(
            slack_channel = "alerts",
            token = token,
        )

    def filter_alert_stream(self, target):
        target_extra = target.targetextra_set.filter(key='Host Galaxies').first()
        if target_extra is None:
            return
        for galaxy in json.loads(target_extra.value):
            if galaxy['Source'] in ['GLADE', 'GWGC', 'HECATE'] and galaxy['Dist'] <= self.max_dist:  # catalogs that have dist
                slack_alert = (f'{target.name} is {galaxy["Offset"]:.1f}" from '
                               f'galaxy {galaxy["ID"]} at {galaxy["Dist"]:.1f} Mpc.')
                break
        else:
            return

        # if there was nearby host galaxy found, calculate the absolute magnitude at discovery
        photometry = target.reduceddatum_set.filter(data_type='photometry')
        first_det = photometry.filter(value__magnitude__isnull=False).order_by('timestamp').first()
        if first_det:
            time_fdet = (datetime.now(tz=first_det.timestamp.tzinfo) - first_det.timestamp).total_seconds() / 3600. / 24.
            absmag = first_det.value['magnitude'] - 5. * (np.log10(galaxy["Dist"]) + 5.)
            slack_alert += (f' If this is the host, the transient was detected {time_fdet:.1f} days ago at '
                            f'an absolute magnitude of {absmag:.1f} mag in {first_det.value["filter"]}.')

            # if there was a nondetection, calculate the rise rate
            last_nondet = photometry.filter(value__magnitude__isnull=True,
                                            timestamp__lt=first_det.timestamp).order_by('timestamp').last()
            if last_nondet:
                time_lnondet = (first_det.timestamp - last_nondet.timestamp).total_seconds() / 3600. / 24.
                dmag_lnondet = (last_nondet.value['limit'] - first_det.value['magnitude']) / time_lnondet
                slack_alert += f' The last nondetection was {time_lnondet:.1f} days before detection,'
                if dmag_lnondet > 0:
                    slack_alert += f' during which time it rose &gt;{dmag_lnondet:.1f} mag/day.'
                else:
                    slack_alert += ' but it does not constrain the rise rate.'
            else:
                slack_alert += ' No nondetection was reported.'
        target.tns_objname = split_name(target.name)['tns_objname']
        slack_alert += ' ' + ALERT_LINKS.format(target=target)
        return slack_alert
