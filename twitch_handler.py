from twitch.api import v3 as twitch
from twitch.logging import log as twitch_log
import threading
import logging
from time import sleep
import datetime
from pprint import pformat


class TwitchHandler(object):

    def __init__(self, name_list):
        super(TwitchHandler, self).__init__()
        twitch_log.setLevel(logging.INFO)
        self.logger = logging.getLogger("TwitchHandler")
        self.follower_cache = {}
        self.thread = threading.Thread(target=self.run)
        self.running = False
        self.follower_callbacks = []
        self.streaming_start_callbacks = []
        self.streaming_stop_callbacks = []
        self.viewers_change_callbacks = []
        self.online_status = {}
        self.viewer_cache = {}
        for name in name_list:
            if twitch.streams.by_channel(name).get("stream"):
                self.online_status[name] = True
            else:
                self.online_status[name] = False
            self.follower_cache[name] = {
                f['user']['display_name'] or f['user']['name']
                for f in twitch.follows.by_channel(name,
                                                   limit=25)['follows']
            }

    def subscribe_new_follow(self, callback):
        self.follower_callbacks.append(callback)

    def subscribe_streaming_start(self, callback):
        self.streaming_start_callbacks.append(callback)

    def subscribe_streaming_stop(self, callback):
        self.streaming_stop_callbacks.append(callback)

    def subscribe_viewers_change(self, callback):
        self.viewers_change_callbacks.append(callback)

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self.run)
        self.thread.daemon = True
        self.thread.start()

    def run(self):
        self.logger.info("Starting twitch api polling")
        self.running = True
        self.next_check = datetime.datetime.now()
        if self.streaming_stop_callbacks or self.streaming_start_callbacks or self.follower_callbacks:
            while self.running:
                if self.next_check < datetime.datetime.now():
                    if self.streaming_start_callbacks or self.streaming_stop_callbacks or self.viewers_change_callbacks:
                        for name in self.online_status:
                            result = twitch.streams.by_channel(name).get("stream")
                            self.check_streaming(name, result)
                            self.check_viewers(name, result)
                    if self.follower_callbacks:
                        self.check_followers()
                        self.next_check = datetime.datetime.now() + datetime.timedelta(seconds=60)
                sleep(10)

        else:
            self.logger.critical("Not starting, no callbacks registered")

    def check_streaming(self, name, result):
        if result:
            if not self.online_status[name]:
                self.online_status[name] = True
                for callback in self.streaming_start_callbacks:
                    callback(name)
        elif self.online_status[name]:
            self.online_status[name] = False
            for callback in self.streaming_stop_callbacks:
                callback(name)

    def check_followers(self):
        for streamer_name in self.online_status:
            latest_follows = {
                f['user']['display_name'] or f['user']['name']
                for f in twitch.follows.by_channel(streamer_name,
                                                   limit=25)['follows']
            }
            new_follows = latest_follows.difference(self.follower_cache[streamer_name])
            if new_follows:
                self.follower_cache[streamer_name].update(new_follows)
                for callback in self.follower_callbacks:
                    callback(new_follows, streamer_name)

    def check_viewers(self, name, result):
        if self.online_status[name]:
            result = twitch.streams.by_channel(name).get("stream")
            if result:
                if name in self.viewer_cache:
                    if self.viewer_cache[name] != result['viewers']:
                        self.viewer_cache[name] = result['viewers']
                        for callback in self.viewers_change_callbacks:
                            callback(result['viewers'], name)
                else:
                    self.viewer_cache[name] = result['viewers']
                    for callback in self.viewers_change_callbacks:
                        callback(result['viewers'], name)

    def stop(self):
        self.logger.info("Attempting to stop twitch api polling")
        self.running = False
        if self.thread.is_alive():
            self.thread.join()
