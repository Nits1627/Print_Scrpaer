# backend/scraper.py

import json
import logging
from typing import List
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")


class WebScraper:
    """
    Hybrid scraper that:
      1) Tries Google Custom Search API (image search) if api_key & cse_id are provided.
      2) If Google fails (quota or missing credentials), falls back to Bing image scraping via ScrapingBee.
      3) Filters results so that the hosting page URL contains at least one word from the brand name.
    """

    def __init__(
        self,
        brand_name: str,
        google_api_key: str = None,
        google_cse_id: str = None,
        scrapingbee_api_key: str = None,
    ):
        """
        :param brand_name: e.g. "Himalya Herbals Personal Care"
        :param google_api_key: Google Custom Search JSON API key (optional)
        :param google_cse_id: Google Custom Search Engine ID (optional)
        :param scrapingbee_api_key: Your ScrapingBee API key (optional, used for Bing fallback)
        """
        self.brand_name = brand_name.strip()
        self.brand_keywords = [w.lower() for w in self.brand_name.split() if w]

        # Google credentials
        self.google_api_key = google_api_key.strip() if google_api_key else None
        self.google_cse_id = google_cse_id.strip() if google_cse_id else None
        self.google_base_url = "https://www.googleapis.com/customsearch/v1"

        # ScrapingBee credentials
        self.scrapingbee_api_key = scrapingbee_api_key.strip() if scrapingbee_api_key else None
        self.scrapingbee_base = "https://app.scrapingbee.com/api/v1/"

        # Bing search phrases (for fallback)
        self.bing_search_keywords = [
            f"{self.brand_name} newspaper ad",
            f"{self.brand_name} magazine ad",
            f"{self.brand_name} print ad",
            f"{self.brand_name} social media ad",
        ]

        # Common HTTP session
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        })

    # ------------------ GOOGLE PART ------------------

    def _google_image_search(self, query: str, num: int = 10, start: int = 1):
        """
        Call Google Custom Search API (image search).
        Raises RuntimeError on any non-200 (including 429 quota).
        Returns list of items (may be empty).
        """
        params = {
            "key": self.google_api_key,
            "cx": self.google_cse_id,
            "q": query,
            "searchType": "image",
            "start": start,
            "num": num,
        }
        resp = requests.get(self.google_base_url, params=params, timeout=10)

        # Quota exceeded or other errors
        if resp.status_code == 429:
            raise RuntimeError("Google Custom Search API quota exceeded (429).")
        if resp.status_code != 200:
            raise RuntimeError(f"Google API error {resp.status_code}: {resp.text}")

        data = resp.json()
        return data.get("items", [])

    def _scrape_with_google(self, max_images: int = 30) -> List[str]:
        """
        Attempt to collect up to max_images using Google Custom Search.
        Returns a list of image URLs. Raises on errors so we can fallback.
        """
        collected = []
        seen = set()
        per_page = 10
        pages = (max_images + per_page - 1) // per_page

        search_queries = [
            f"{self.brand_name} newspaper ad",
            f"{self.brand_name} magazine ad",
            f"{self.brand_name} print ad",
            f"{self.brand_name} social media ad",
        ]

        for query in search_queries:
            if len(collected) >= max_images:
                break
            logger.info(f"▶ [Google] Searching for: \"{query}\"")
            for page_idx in range(pages):
                if len(collected) >= max_images:
                    break
                start_idx = page_idx * per_page + 1
                logger.info(f"   • [Google] Fetching results {start_idx} to {start_idx + per_page - 1}")
                items = self._google_image_search(query, num=per_page, start=start_idx)
                if not items:
                    break

                for item in items:
                    if len(collected) >= max_images:
                        break
                    img_url = item.get("link", "")
                    page_url = item.get("image", {}).get("contextLink", "")
                    if not img_url or not page_url:
                        continue
                    page_lower = page_url.lower()
                    if not any(kw in page_lower for kw in self.brand_keywords):
                        continue
                    if img_url in seen:
                        continue
                    seen.add(img_url)
                    collected.append(img_url)
                    logger.info(f"  ➤ [Google] Collected: {img_url}  (page: {page_url})")

        logger.info(f"✅ [Google] Collected {len(collected)} URLs (target={max_images}).")
        return collected

    # ------------------ BING + SCRAPINGBEE PART ------------------

    def _fetch_via_scrapingbee(self, target_url: str) -> str:
        """
        Fetch the rendered HTML of target_url via ScrapingBee.
        Raises RuntimeError on failure.
        """
        params = {
            "api_key": self.scrapingbee_api_key,
            "url": target_url,
            # You can add "render_js": "false" or "true" if you need JS rendering
            # e.g. "render_js": "false"
        }
        resp = requests.get(self.scrapingbee_base, params=params, timeout=20)
        if resp.status_code != 200:
            raise RuntimeError(f"ScrapingBee error {resp.status_code}: {resp.text}")
        return resp.text

    def _scrape_with_bing(self, max_images: int = 30) -> List[str]:
        """
        Fallback scraping using Bing + ScrapingBee (or direct requests if no key).
        - Uses <a class="iusc" m="..."> extraction.
        - Filters by page URL containing a brand keyword.
        """
        collected = []
        seen = set()

        for keyword in self.bing_search_keywords:
            if len(collected) >= max_images:
                break

            bing_url = f"https://www.bing.com/images/search?q={quote_plus(keyword)}"
            logger.info(f"▶ [Bing] Fetching: {bing_url}")

            try:
                if self.scrapingbee_api_key:
                    # Use ScrapingBee to avoid blocks
                    html = self._fetch_via_scrapingbee(bing_url)
                else:
                    # Direct requests (more likely to be blocked)
                    r = self.session.get(bing_url, timeout=10)
                    if r.status_code != 200:
                        logger.error(f"[Bing] Status {r.status_code} for {bing_url}")
                        continue
                    html = r.text
            except Exception as e:
                logger.error(f"[Bing] Failed to fetch {bing_url}: {e}")
                continue

            soup = BeautifulSoup(html, "html.parser")
            a_tags = soup.find_all("a", class_="iusc")
            logger.info(f"🔍 [Bing] Found {len(a_tags)} <a class='iusc'> tags.")

            for a in a_tags:
                if len(collected) >= max_images:
                    break

                m_attr = a.get("m")
                if not m_attr:
                    continue

                try:
                    m_data = json.loads(m_attr)
                except json.JSONDecodeError:
                    continue

                murl = m_data.get("murl")
                purl = m_data.get("purl")
                if not murl or not purl:
                    continue

                p_lower = purl.lower()
                if not any(kw in p_lower for kw in self.brand_keywords):
                    continue
                if murl in seen:
                    continue

                seen.add(murl)
                collected.append(murl)
                logger.info(f"  ➤ [Bing] Collected: {murl}  (page: {purl})")

            logger.info(f"✅ [Bing] Collected {len(collected)} URLs so far (target={max_images}).")

        return collected

    # ------------------ PUBLIC METHOD ------------------

    def scrape_images(self, max_images: int = 30) -> List[str]:
        """
        Main entrypoint:
          1) If both google_api_key and google_cse_id are provided, try Google first.
          2) On any error (quota, invalid creds, etc.), fall back to Bing via ScrapingBee.
          3) If Google creds are missing, skip Google altogether and go straight to Bing.
        """
        # 1) Try Google if credentials exist
        if self.google_api_key and self.google_cse_id:
            try:
                logger.info("Attempting to scrape via Google Custom Search...")
                return self._scrape_with_google(max_images)
            except Exception as e:
                logger.warning(f"❗ Google scraping failed, falling back to Bing: {e}")

        # 2) Fallback to Bing (via ScrapingBee if key present)
        logger.info("Falling back to Bing scraping (via ScrapingBee if configured)...")
        return self._scrape_with_bing(max_images)