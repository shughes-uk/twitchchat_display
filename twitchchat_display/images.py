from functools import lru_cache
from io import BytesIO

import pygame
import requests


class ChatImage:
    def __init__(self, client_id, height=16):
        self.session = requests.Session()
        self.session.headers["Client-ID"] = client_id
        self.session.headers["Accept"] = "application/vnd.twitchtv.v5+json"
        self.img_height = height

    def load_from_url(self, url):
        resp = self.session.get(url)
        f = BytesIO(resp.content)
        surface = pygame.image.load(f)
        ratio = self.img_height / float(surface.get_height())
        new_size = (int(surface.get_width() * ratio), self.img_height)
        resized = pygame.transform.scale(surface, new_size)
        if not pygame.display.get_init():
            return resized
        else:
            return resized.convert_alpha()


class TwitchEmotes(ChatImage):
    def __init__(self, client_id, height):
        super().__init__(client_id=client_id, height=height)
        result = self.session.get("https://api.twitch.tv/kraken/chat/emoticons").json()
        self.emote_map = {str(e["id"]): e["images"]["url"] for e in result["emoticons"]}

    @lru_cache(maxsize=1000)
    def get(self, code):
        url = self.emote_map.get(code)
        if url:
            return self.load_from_url(self.emote_map[code])


class TwitchBadges(ChatImage):
    def __init__(self, client_id, height):
        super().__init__(client_id=client_id, height=height)
        self.global_badges = self.session.get(
            "https://badges.twitch.tv/v1/badges/global/display?language=en"
        ).json()["badge_sets"]
        self.badge_map = {}

    def _get_channel_badges(self, channel_id):
        if channel_id not in self.badge_map:
            self.badge_map[channel_id] = self.session.get(
                f"https://api.twitch.tv/kraken/chat/{channel_id}/badges"
            ).json()
            return self.badge_map[channel_id]
        else:
            return self.badge_map[channel_id]

    @lru_cache(maxsize=1000)
    def get(self, channel_id, badge_type):
        badge_map = self._get_channel_badges(channel_id)
        badge, version = badge_type.split("/")
        if badge_map.get(badge):
            url = badge_map[badge].get("image")
            return self.load_from_url(url)
        else:
            badge_url = self.global_badges[badge]["versions"][version]["image_url_4x"]
            return self.load_from_url(badge_url)
