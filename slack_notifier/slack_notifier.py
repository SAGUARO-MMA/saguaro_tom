"""
A subclass of the slack_sdk WebClient with extra cusomtization
"""
from tom_targets.models import BaseTarget
from slack_sdk import WebClient
from django.conf import settings
import logging

from astropy import units as u
from astropy.time import Time

logger = logging.getLogger(__name__)

SLACK_THREADING_DELTA_T = 90 # days ~ 3 months

class SlackNotifier(WebClient):

    def __init__(self, slack_channel:str, token:str):

        self.slack_channel = slack_channel

        super().__init__(token=token)
        
    def filter_alert_stream(self, text):
        """
        This is the default, and just doesn't do any filtering
        """
        return text
        
    def send_slack_message_from_text(self, msg, thread_id=None):
        if thread_id is not None:
            self.chat_postMessage(
                channel = self.slack_channel,
                text = msg,
                thread_ts = thread_id,
                reply_broadcast = True
            )
        else:
            self.chat_postMessage(
                channel = self.slack_channel,
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

        thread_id = None
        import pdb; pdb.set_trace()
        if "target" in kwargs or any(isinstance(arg, BaseTarget) for arg in args):
            target = kwargs["target"]
            logger.info(
                f"Searching for messages in the past {SLACK_THREADING_DELTA_T}days that mentioned {target.name}"
            )
            thread_id = self._find_relevant_thread(target=target)

        self.send_slack_message_from_text(msg, thread_id=thread_id)

    def _find_relevant_thread(self, target):
        result = self.conversations_history(
            channel = self.slack_channel,
            inclusive = True,
            oldest = (Time.now() - SLACK_THREADING_DELTA_T*u.day).unix
        )

        for msg in result["messages"]:
            if msg["text"].contains(target.name):
                # this message contained this target name, so send it in thread here
                return msg["ts"]
