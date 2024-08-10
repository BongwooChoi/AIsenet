import streamlit as st
import google.generativeai as genai
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
import os
from datetime import datetime, timedelta
import requests
from operator import itemgetter

# ... (이전 코드는 그대로 유지)

# 뉴스 검색 함수 (Google News API 사용)
def search_news(query, published_after, max_results=10):
    api_key = st.secrets["GOOGLE_NEWS_API_KEY"]
    url = f"https://newsapi.org/v2/everything?q={query}&from={published_after}&language=ko&sortBy=publishedAt&apiKey={api_key}&pageSize={max_results * 2}"
    
    response = requests.get(url)
    news_data = response.json()
    articles = news_data.get('articles', [])
    
    # 결과를 출판일 기준으로 정렬 (최신순)
    sorted_articles = sorted(articles, key=lambda x: x['publishedAt'], reverse=True)
    
    # 중복 제거 (URL 기준)
    unique_articles = []
    seen_urls = set()
    for article in sorted_articles:
        if article['url'] not in seen_urls:
            unique_articles.append(article)
            seen_urls.add(article['url'])
        if len(unique_articles) == max_results:
            break
    
    return unique_articles

# ... (나머지 코드는 그대로 유지)

# 검색 실행
if search_button:
    keywords = " ".join(filter(None, [keyword1, keyword2, keyword3]))
    if keywords:
        with st.spinner(f"{source}를 검색하고 있습니다..."):
            published_after = get_published_after(period)
            
            if source == "YouTube":
                # YouTube 영상 검색 (변경 없음)
                videos, total_video_results = search_videos_with_transcript(keywords, published_after)
                st.session_state.search_results = {'videos': videos, 'news': []}
                st.session_state.total_results = total_video_results
            
            elif source == "뉴스":
                # 뉴스 검색
                news_articles = search_news(keywords, published_after, max_results=10)
                total_news_results = len(news_articles)
                st.session_state.search_results = {'videos': [], 'news': news_articles}
                st.session_state.total_results = total_news_results
            
            # 검색 실행 시 요약 결과 초기화
            st.session_state.summary = ""
            if not st.session_state.total_results:
                st.warning(f"{source}에서 결과를 찾을 수 없습니다. 다른 키워드로 검색해보세요.")
    else:
        st.warning("키워드를 입력해주세요.")

# ... (이하 코드는 그대로 유지)
