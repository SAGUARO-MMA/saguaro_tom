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

        if (has_vs_match or has_agn_match) and telescope_stream == "ZTF":
            # don't send this message!
            return
        
        if created:
            base_str = f"{target.name} created from the Antares alert stream."
        elif not created and len(aliases_added):
            base_str = f"{target.name} has been updated from the Antares alert stream with the following aliases: {', '.join(aliases_added)}"
        else:
            base_str = f"{target.name} has been updated from the Antares alert stream."

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
            
        # variable star and AGN matches
        if has_agn_match:
            base_str += f"\nAGN Match: {agn_match.value}"

        if has_vs_match:
            base_str += "Variable Star Matches:\n"
            for vs_match in vs_matches:
                if vs_match.value == 'None': continue
                base_str += f"\t* {vs_match.value} offset by "
                if vs_match.key == "Gaia Match":
                    vs_offset = target.targetextra_set.filter(key='Gaia VS Offset').first()
                    base_str += f"{float(vs_offset.value):.3f}\"\n"
                else:
                    base_str += f"<2\"\n"
                    
                
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
