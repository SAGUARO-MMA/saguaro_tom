"""
Other slack functionality, for backwards compatibility
"""

from django.conf import settings
from slack_sdk import WebClient

import logging
logger = logging.getLogger(__name__)

def send_slack_gw(body, format_kwargs, is_test_alert=False, is_significant=True, is_burst=False, has_ns=True,
               all_workspaces=True, at=None):

    slack_gw = [WebClient(token) for token in settings.SLACK_TOKENS_GW]

    if is_test_alert:
        channel = None
    elif not is_significant:
        channel = 'alerts-subthreshold'
    elif is_burst:
        channel = 'alerts-burst'
    elif not has_ns:
        channel = 'alerts-bbh'
    else:
        channel = 'alerts-ns'
    if at is not None:
        body = f'<!{at}>\n' + body
    for slack_client, (nle_link, service), (target_link, _) in zip(slack_gw, settings.NLE_LINKS, settings.TARGET_LINKS):
        body_slack = body.format(nle_link=nle_link, service=service, target_link=target_link).format(**format_kwargs)
        logger.info(f'Sending GW alert: {body_slack}')
        if channel is None:
            break  # just print out test alerts for debugging
        slack_client.chat_postMessage(channel=channel, text=body_slack)
        if not all_workspaces:
            break


def pick_slack_channel(seq):
    is_test_alert = seq.nonlocalizedevent.event_id.startswith('M')
    is_significant = seq.details['significant']
    is_burst = seq.details['group'] == 'Burst'
    has_ns = seq.details['properties'].get('HasNS', 0.) >= 0.01 \
             or seq.details['classification'].get('BNS', 0.) >= 0.01 \
             or seq.details['classification'].get('NSBH', 0.) >= 0.01
    return is_test_alert, is_significant, is_burst, has_ns
