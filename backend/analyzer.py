# backend/analyzer.py

"""
A no‐op Analyzer stub to satisfy imports.
We’re dropping OCR/AI for this “normal web scrape” fallback.
"""

class AIAnalyzer:
    def __init__(self, *args, **kwargs):
        pass

    def extract_text_from_image(self, image_path: str) -> str:
        return ""

    def analyze_brand_relevance(self, text: str, brand_name: str) -> float:
        return 0.0

    def classify_as_advertisement(self, image_path: str, text_content: str) -> float:
        return 0.0