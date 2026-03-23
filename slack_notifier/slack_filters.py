"""
Custom filters (i.e., subclasses of SlackNotifier)
"""
import json
from datetime import datetime, timedelta
from astropy.time import Time
import numpy as np

from .slack_notifier import SlackNotifier
from tom_targets.templatetags.targets_extras import deg_to_sexigesimal
from custom_code.templatetags.target_extras import split_name
from django.db.models import Q
from django.conf import settings

ALERT_LINKS = ' '.join([f'<{link}|{service}>' for link, service in settings.TARGET_LINKS])

class AntaresSlackFilter(SlackNotifier):

    def __init__(self, token=settings.SLACK_TOKEN_TNS):
        super().__init__(
            slack_channel = "alerts",
            token = token
        )

    def filter_alert_stream(self, target, created, aliases_added, telescope_stream = "ZTF"):
        target_extra = target.targetextra_set.filter(key='Host Galaxies').first()
        vs_matches = target.targetextra_set.filter(key__in=[
            "Gaia Match", "PS1 Match", "ASASSN Match"
        ])
        agn_match = target.targetextra_set.filter(key="QSO Match").first()

        has_vs_match = any(m.value != 'None' for m in vs_matches)
        has_agn_match = agn_match is not None and agn_match.value != 'None'

        peak = target.reduceddatum_set.order_by('value__magnitude').first()
        peak_mag = peak.value['magnitude'] if peak else np.nan

        #Check that the first alert is now
        first_alert_mjd = Time(target.reduceddatum_set.filter(data_type="photometry", value__magnitude__isnull = False).earliest()).mjd

        # want to ignore non-detections
        # And then also throw out anything with a low SNR before a day
        previous_detections = target.reduceddatum_set.filter(
            Q(data_type="photometry") &
            Q(value__magnitude__isnull = False) &
            Q(timestamp__lt = datetime.now()-timedelta(1)) &
            Q(value__error__lt = 0.1)
        )
        new_alert = previous_detections.count() == 0

        if not new_alert:
            latest_det_mjd = target.reduceddatum_set.filter(data_type="photometry", value__magnitude__isnull = False).latest()
            latest_det_mag = target.reduceddatum_set.filter(data_type="photometry", value__magnitude__isnull = False).latest().value['magnitude']

            second_to_last_det_mjd = target.reduceddatum_set.filter(data_type="photometry", timestamp__lt = latest.timestamp).latest()
            second_to_last_det_mag = target.reduceddatum_set.filter(data_type="photometry", timestamp__lt = latest.timestamp).latest().value['magnitude']

            delta_mag = latest_det_mag - second_to_last_det_mag
            delta_t = latest_det_mjd - second_to_last_det_mjd
            rise_rate = delta_mag/delta_t #mag/day

        if has_vs_match or has_agn_match:
            # don't send this message!
            return
        
        #Report all new objects
        #We create things with a lot of past detections so created != new_target
        if new_alert:
            base_str = f"First Detection of {target.name} in the {telescope_stream} alert stream."
        #if not new, look for rapidly rising
        elif rise_rate<-0.5: 
            base_str = f"Rapidly rising object {target.name} in the {telescope_stream} alert stream ({rise_rate:0.2f}<-0.5 mag/day)"
            if len(aliases_added):
                base_str += f" aliases: {', '.join(aliases_added)}"
        # Even if sparsely spaced, catch things that significantly change
        elif delta_mag < -0.5:
            base_str = f"Rapidly rising object {target.name} in the {telescope_stream} alert stream ({delta_mag:1.2f}<-0.5 mag since last detection {delta_t:1.2f} days ago)"
            if len(aliases_added):
                base_str += f" aliases: {', '.join(aliases_added)}"
        else:
            # don't send this message!
            return

        if np.isfinite(peak_mag):
            base_str += f"\n Brightest mag ({peak_mag:.1f} mag)"

        # host info
        if target_extra.value != 'None':
            n = 0
            host_str = "\nThe three most likely host galaxies are:\n"
            for galaxy in json.loads(target_extra.value):
                host_str += f"\t{n+1}. {galaxy['Offset']:.3f}\" from {galaxy['ID']} at {galaxy['Dist']:.1f} Mpc\n"
                n += 1
                if n > 2:
                    break
            base_str += host_str
        else:
            base_str += f"\nNo host galaxies are found in SAGUARO for {target.name}\n"

        base_str += "\n"
                
        # photometry info
        # TODO: Put some text in the slack message about the rise rate, etc.
        target.tns_objname = split_name(target.name)['tns_objname']
        base_str += ' ' + ALERT_LINKS.format(target=target)
        return base_str
                
class DistanceLimitedSlackFilter(SlackNotifier):

    def __init__(self, max_dist, token=settings.SLACK_TOKEN_TNS):
        self.max_dist = max_dist
        super().__init__(
            slack_channel = ["alerts", "alerts-tns"],
            token = token,
        )
        
    def filter_alert_stream(self, target):
        target_extra = target.targetextra_set.filter(key='Host Galaxies').first()
        if target_extra is None:
            return
        for galaxy in json.loads(target_extra.value):
            if galaxy['Source'] in ['GLADE', 'GWGC', 'HECATE'] and galaxy['Dist'] <= self.max_dist:  # catalogs that have dist
                slack_alert = (f'{target.name} ({deg_to_sexigesimal(target.ra, "hms")} {deg_to_sexigesimal(target.dec, "dms")}) '
                               f'is {galaxy["Offset"]:.1f}" from galaxy {galaxy["ID"]} at {galaxy["Dist"]:.1f} Mpc.')
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
