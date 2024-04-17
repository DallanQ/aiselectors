import json
from urllib.parse import urlparse

from aiselectors.page import Page


def _get_domain(url):
    return urlparse(url).netloc


def _get_cache_key(url, prompt):
    return f"{_get_domain(url)}|{prompt}"


class AISelectors:
    def __init__(
        self,
        client,
        model="gpt-4-turbo-preview",
        max_tokens=1024,
        n_css_attempts=3,
        n_xpath_attempts=3,
        n_text_attempts=3,
    ):
        self.client = client
        self.model = model
        self.max_tokens = max_tokens
        self.n_css_attempts = n_css_attempts
        self.n_xpath_attempts = n_xpath_attempts
        self.n_text_attempts = n_text_attempts
        self._cache = {}

    def clear_cache(self):
        self._cache = {}

    def load_cache(self, cache_path):
        # load the cache from a file
        with open(cache_path) as f:
            self._cache = json.load(f)

    def save_cache(self, cache_path):
        # save the cache to a file
        with open(cache_path, "w") as f:
            json.dump(self._cache, f)

    def page(self, url, html) -> Page:
        return Page(url, html, self)

    def get_cache_entry(self, url, prompt):
        return self._cache.get(_get_cache_key(url, prompt))

    def set_cache_entry(self, url, prompt, xpath):
        self._cache[_get_cache_key(url, prompt)] = xpath
