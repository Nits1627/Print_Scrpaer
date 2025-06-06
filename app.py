# app.py

import streamlit as st
from backend.scraper import WebScraper

st.set_page_config(page_title="Hybrid Print Ad Finder", layout="wide")
st.title("📰 Hybrid Print Ad Finder (Google → ScrapingBee/Bing Fallback)")

st.markdown(
    """
    This app tries to fetch official print‐ad images using **Google Custom Search API**.  
    If Google fails (quota, invalid credentials, etc.), it *automatically* falls back to a **Bing scrape via ScrapingBee** (if you provide a ScrapingBee key) or plain requests otherwise.  
    In all cases, we filter results so that the hosting page URL contains at least one word from your brand name.  
    """
)

# Sidebar inputs
st.sidebar.header("Configuration")

brand_name = st.sidebar.text_input("🔍 Brand Name", value="Himalya Herbals Personal Care")

# Google credentials (optional)
api_key = st.sidebar.text_input("🔐 Google API Key (optional)", type="password")
cse_id = st.sidebar.text_input("🆔 Google CSE ID (optional)")

# ScrapingBee key (optional, used for Bing fallback)
scrapingbee_key = st.sidebar.text_input("🗝️ ScrapingBee API Key (optional)", type="password")

max_images = st.sidebar.slider("📸 Max Images to Display", min_value=5, max_value=100, value=30)

if st.sidebar.button("🚀 Find Print Ads"):
    if not brand_name.strip():
        st.error("Please enter a Brand Name.")
    else:
        st.subheader(f"Searching for print ads of “{brand_name}” …")

        scraper = WebScraper(
            brand_name=brand_name,
            google_api_key=api_key,
            google_cse_id=cse_id,
            scrapingbee_api_key=scrapingbee_key,
        )

        with st.spinner("Fetching images (Google first, then ScrapingBee/Bing)..."):
            urls = scraper.scrape_images(max_images=max_images)

        if not urls:
            st.error(
                "❌ No print‐ad images found. Possible reasons:\n"
                "  • Google quota exceeded or invalid credentials (and no ScrapingBee key provided), \n"
                "  • Bing was blocked (or too strict a filter), or \n"
                "  • brand keywords did not match any page URLs.\n"
                "Try increasing Max Images or checking your keys."
            )
        else:
            st.success(f"✅ Retrieved {len(urls)} images. Displaying below:")

            # Display images in a 3-column grid
            cols = st.columns(3)
            for i, img_url in enumerate(urls):
                col = cols[i % 3]
                with col:
                    st.image(img_url, width=250)
                    st.caption(img_url)