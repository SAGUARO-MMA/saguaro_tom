"""
A subclass of the slack_sdk WebClient with extra cusomtization
"""
from tom_targets.models import BaseTarget
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from django.conf import settings
import logging

from custom_code.templatetags.target_extras import split_name

from astropy import units as u
from astropy.time import Time

logger = logging.getLogger(__name__)

SLACK_THREADING_DELTA_T = 90 # days ~ 3 months

class SlackNotifier(WebClient):

    def __init__(self, slack_channel:str, token:str):

        self.slack_channels = slack_channel if isinstance(slack_channel, list) else [slack_channel]

        self.channel_name_to_id = {
            "alerts":"C0ACQ9HKMPS"
        }
        
        super().__init__(token=token)
        
    def filter_alert_stream(self, text):
        """
        This is the default, and just doesn't do any filtering
        """
        return text
        
    def send_slack_message_from_text(self, msg, thread_ids=None):
        if thread_ids is None:
            thread_ids = [None]*self.slack_channels
            
        for channel, thread_id in zip(self.slack_channels, thread_ids):
            if thread_id is not None:
                self.chat_postMessage(
                    channel = channel,
                    text = msg,
                    thread_ts = thread_id,
                    reply_broadcast = True
                )
            else:
                self.chat_postMessage(
                    channel = channel,
                    text = msg,
                )
    
    def send_slack_message(self, *args, **kwargs):
        test = "test" in kwargs and kwargs["test"]
        if "test" in kwargs:
            del kwargs["test"]
        
        msg = self.filter_alert_stream(*args, **kwargs)
        if msg is None:
            logger.info("No new alerts to send!")
            return
        
        logger.info(msg)

        if test:
            return

        thread_id = [None]*len(self.slack_channels)
        if "target" in kwargs or any(isinstance(arg, BaseTarget) for arg in args):
            if "target" in kwargs:
                target = kwargs["target"]
            else:
                for arg in args:
                    if isinstance(arg, BaseTarget):
                        target = arg
                        break
            
            logger.info(
                f"Searching for messages in the past {SLACK_THREADING_DELTA_T}days that mentioned {target.name}"
            )

            for ii, channel in enumerate(self.slack_channels):
                try:
                    thread_id[ii] = self._find_relevant_thread(target=target, chan=channel)
                except Exception as apierr:
                    logger.warning("This token may not have the permissions to read the history of {channel}! Skipping!")
                    logger.exception(apierr)

        self.send_slack_message_from_text(msg, thread_ids=thread_id)

    def _find_relevant_thread(self, target, chan):
        if chan not in self.channel_name_to_id:
            return
        
        result = self.conversations_history(
            channel = self.channel_name_to_id.get(chan),
            inclusive = True,
            oldest = (Time.now() - SLACK_THREADING_DELTA_T*u.day).unix
        )

        partial_name = split_name(target.name)['basename']

        for msg in result["messages"]:
            if partial_name in msg["text"]:
                # this message contained this target name, so send it in thread here
                return msg["ts"]
