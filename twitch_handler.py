from twitch.api import v3 as twitch
from twitch.logging import log as twitch_log
import threading
import logging
from time import sleep
import datetime
twitch_log.setLevel(logging.INFO)


class TwitchHandler(object):

    def __init__(self, name_list):
        super(TwitchHandler, self).__init__()
        self.logger = logging.getLogger("TwitchHandler")
        self.follower_cache = {}
        self.thread = threading.Thread(target=self.run)
        self.running = False
        self.follower_callbacks = []
        self.streaming_callbacks = []
        self.online_status = {}
        for name in name_list:
            if twitch.streams.by_channel(name).get("stream"):
                self.online_status[name] = True
            else:
                self.online_status[name] = False
            self.follower_cache[name] = twitch.follows.by_channel(name, limit=25)['follows']

    def subscribe_new_follow(self, callback):
        self.follower_callbacks.append(callback)

    def subscribe_streaming_status(self, callback):
        self.streaming_callbacks.append(callback)

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self.run)
        self.thread.start()

    def run(self):
        self.logger.info("Starting twitch api polling")
        self.running = True
        self.next_check = datetime.datetime.now() + datetime.timedelta(seconds=60)
        if self.streaming_callbacks or self.follower_callbacks:
            while self.running:
                if self.next_check < datetime.datetime.now():
                    if self.streaming_callbacks:
                        self.check_streaming()
                    if self.follower_callbacks:
                        self.check_followers()
                        self.next_check = datetime.datetime.now() + datetime.timedelta(seconds=60)
                sleep(1)

        else:
            self.logger.critical("Not starting, no callbacks registered")

    def check_streaming(self):
        for name in self.online_status:
            result = twitch.streams.by_channel(name).get("stream")
            if result:
                if not self.online_status[name]:
                    self.online_status[name] = True
                    for callback in self.streaming_callbacks:
                        callback(name, True)
            elif self.online_status[name]:
                self.online_status[name] = False
                for callback in self.streaming_callbacks:
                    callback(name, False)

    def check_followers(self):
        for streamer_name in self.online_status:
            latest_follows = twitch.follows.by_channel(streamer_name, limit=25)['follows']
            if latest_follows != self.follower_cache[streamer_name]:
                new_follows = []
                for follow in latest_follows:
                    if follow not in self.follower_cache[streamer_name]:
                        new_follows.append(follow['user'])
                self.follower_cache[streamer_name] = latest_follows
                for callback in self.follower_callbacks:
                    callback(new_follows, streamer_name)

    def stop(self):
        self.logger.info("Attempting to stop twitch api polling")
        self.running = False
        if self.thread.is_alive():
            self.thread.join()
