import streamlit as st
import google.generativeai as genai
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
import os
from datetime import datetime, timedelta, timezone, UTC
import time
import requests
import urllib.parse
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf

# Streamlit 앱 설정
st.set_page_config(page_title="AI 금융정보 검색 및 분석 서비스", page_icon="🤖", layout="wide")

# API 키 설정
genai.configure(api_key=st.secrets["GOOGLE_AI_STUDIO_API_KEY"])
youtube = build('youtube', 'v3', developerKey=st.secrets["YOUTUBE_API_KEY"])

# 금융 도메인별 키워드 정의
FINANCE_DOMAINS = {
    "주식": ["주식", "증권", "배당주", "주가", "상장", "차트", "코스피", "코스닥", "러셀", "나스닥", "S&P500", "다우존스", "닛케이"],
    "부동산": ["부동산", "아파트", "주택", "오피스텔", "분양", "청약", "재건축", "재개발", "임대", "상가"],
    "코인": ["암호화폐", "가상화폐", "가상자산", "비트코인", "이더리움", "블록체인", "코인", "거래소", "채굴", "NFT"],
    "채권/금리/환율": ["채권", "국채", "회사채", "금리", "한국은행", "한은", "연준", "환율", "통화", "달러", "엔화", "위안화", "유로화"],
    "경제일반": ["경제", "금융", "무역", "물가", "인플레이션", "국내총생산", "GDP", "소비자물가지수", "생산자물가지수","CPI", "고용", "수출", "소비"]
}

# 주요 주식 리스트
MAJOR_STOCKS = [
    "Apple Inc. (AAPL)",
    "Microsoft Corporation (MSFT)",
    "Amazon.com Inc. (AMZN)",
    "Alphabet Inc. (GOOGL)",
    "Meta Platforms, Inc. (META)",
    "Tesla, Inc. (TSLA)",
    "NVIDIA Corporation (NVDA)",
    "JPMorgan Chase & Co. (JPM)",
    "Johnson & Johnson (JNJ)",
    "Visa Inc. (V)",
    "Realty Income Corporation (O)",
    "Starbucks Corporation (SBUX)",
    "McDonald's Corporation (MCD)"
]

# 뉴스 검색 함수 (Serp API 사용)
def search_news(domain, additional_query, published_after, max_results=20):
    api_key = st.secrets["SERP_API_KEY"]
    keywords = " OR ".join(FINANCE_DOMAINS[domain])
    
    if additional_query:
        query = f"({keywords}) AND ({additional_query})"
    else:
        query = keywords
    
    encoded_query = urllib.parse.quote(query)
    
    url = f"https://serpapi.com/search.json?q={encoded_query}&tbm=nws&api_key={api_key}&num={max_results}&sort=date"
    
    if published_after:
        url += f"&tbs=qdr:{published_after}"
    
    response = requests.get(url)
    news_data = response.json()
    articles = news_data.get('news_results', [])
    
    unique_articles = []
    seen_urls = set()
    for article in articles:
        if article['link'] not in seen_urls:
            unique_articles.append({
                'title': article.get('title', ''),
                'source': {'name': article.get('source', '')},
                'description': article.get('snippet', ''),
                'url': article.get('link', ''),
                'content': article.get('snippet', '')
            })
            seen_urls.add(article['link'])
        if len(unique_articles) == max_results:
            break
    
    return unique_articles

# YouTube 검색 함수
def search_videos(domain, additional_query, published_after, max_results=10):
    try:
        keywords = " OR ".join(FINANCE_DOMAINS[domain])
        query = f"({keywords}) {additional_query}".strip()
        
        videos_with_korean_captions = []
        next_page_token = None
        
        while len(videos_with_korean_captions) < max_results:
            request = youtube.search().list(
                q=query,
                type='video',
                part='id,snippet',
                order='relevance',
                publishedAfter=published_after,
                maxResults=20,
                pageToken=next_page_token
            )
            response = request.execute()
            
            for item in response['items']:
                video_id = item['id']['videoId']
                
                # 한국어 자막 확인 및 저장
                caption = get_video_caption(video_id)
                if caption:
                    item['caption'] = caption  # 자막을 영상 데이터에 저장
                    videos_with_korean_captions.append(item)
                    if len(videos_with_korean_captions) == max_results:
                        break
            
            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break

        return videos_with_korean_captions, len(videos_with_korean_captions)
    except Exception as e:
        st.error(f"YouTube 검색 중 오류 발생: {str(e)}")
        return [], 0


# YouTube 비디오 자막 가져오기 함수
def get_video_caption(video_id):
    try:
        # 비디오의 자막 정보 가져오기
        request = youtube.captions().list(
            part="snippet",
            videoId=video_id
        )
        response = request.execute()

        captions = response.get('items', [])
        if not captions:
            return None

        korean_caption = next((caption for caption in captions if caption['snippet']['language'] == 'ko'), None)
        if not korean_caption:
            return None

        caption_id = korean_caption['id']
        
        # 자막 다운로드 URL 생성
        caption_url = f"https://www.youtube.com/api/timedtext?lang=ko&v={video_id}&id={caption_id}"

        # 자막 데이터 가져오기
        r = requests.get(caption_url)
        if r.status_code == 200:
            return r.text
        else:
            return None
    except Exception as e:
        st.error(f"자막 가져오기 중 오류 발생: {str(e)}")
        return None

# 조회 기간 선택 함수
def get_published_after(option):
    today = datetime.now(UTC)
    if option == "최근 1일":
        date = today - timedelta(days=1)
    elif option == "최근 1주일":
        date = today - timedelta(weeks=1)
    elif option == "최근 1개월":
        date = today - timedelta(weeks=4)
    elif option == "최근 3개월":
        date = today - timedelta(weeks=12)
    elif option == "최근 6개월":
        date = today - timedelta(weeks=24)
    elif option == "최근 1년":
        date = today - timedelta(weeks=52)
    else:
        return None  # 이 경우 조회 기간 필터를 사용하지 않음
    
    # YouTube API가 요구하는 형식으로 변환
    return date.strftime('%Y-%m-%dT%H:%M:%SZ')

# YouTube 영상 요약 함수
def summarize_video(video_id, video_title, caption):
    if not caption:
        return "한국어 자막을 가져올 수 없어 요약할 수 없습니다."

    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        prompt = f"다음 YouTube 영상의 제목과 내용을 가독성 있는 한 페이지의 보고서 형태로 요약하세요:\n\n제목: {video_title}\n\n{caption}"
        response = model.generate_content(prompt)

        if not response or not response.parts:
            feedback = response.prompt_feedback if response else "No response received."
            return f"요약 중 오류가 발생했습니다: {feedback}"

        summary = response.text
        return summary
    except Exception as e:
        return f"요약 중 오류가 발생했습니다: {str(e)}"

# 검색 실행
if search_button:
    if source in ["YouTube", "뉴스"]:
        with st.spinner(f"{source}를 검색하고 있습니다..."):
            published_after = get_published_after(period)
            
            if source == "YouTube":
                videos, total_video_results = search_videos(domain, additional_query, published_after)
                st.session_state.search_results = {'videos': videos, 'news': [], 'financial_info': {}}
                st.session_state.total_results = total_video_results
                st.session_state.summary = ""  # YouTube 검색 시 요약 초기화
            
            elif source == "뉴스":
                # 뉴스 검색 및 자동 분석
                news_articles = search_news(domain, additional_query, published_after, max_results=20)
                total_news_results = len(news_articles)
                st.session_state.search_results = {'videos': [], 'news': news_articles, 'financial_info': {}}
                st.session_state.total_results = total_news_results
                
                # 뉴스 기사 자동 분석
                with st.spinner("뉴스 기사를 종합 분석 중입니다..."):
                    st.session_state.summary = analyze_news_articles(news_articles)
            
            if not st.session_state.total_results:
                st.warning(f"{source}에서 결과를 찾을 수 없습니다. 다른 도메인이나 검색어로 검색해보세요.")
    
    elif source == "재무정보":
        with st.spinner(f"{stock_input}의 재무정보를 검색하고 있습니다..."):
            stock_symbol = search_stock_symbol(stock_input) if not stock_input.isalpha() else stock_input
            if stock_symbol:
                financial_info = search_financial_info(stock_symbol)
                st.session_state.search_results = {'videos': [], 'news': [], 'financial_info': financial_info}
                st.session_state.total_results = 1 if financial_info else 0
                
                if financial_info:
                    with st.spinner("재무정보를 분석 중입니다..."):
                        # 종목명 결정
                        if stock_input_method == "목록에서 선택":
                            stock_name = stock_selection.split('(')[0].strip()  # 괄호 앞의 종목명 추출
                        else:
                            stock = yf.Ticker(stock_symbol)
                            stock_name = stock.info.get('longName', stock_symbol)  # yfinance에서 종목명 가져오기
                        
                        st.session_state.summary = analyze_financial_info(financial_info, stock_symbol, stock_name)
                else:
                    st.warning(f"{stock_input}의 재무정보를 찾을 수 없습니다. 올바른 종목명 또는 종목 코드인지 확인해주세요.")
            else:
                st.warning(f"{stock_input}에 해당하는 종목을 찾을 수 없습니다.")

# 검색 결과 표시
if source == "YouTube":
    st.subheader(f"🎦 검색된 YouTube 영상")
    for video in st.session_state.search_results['videos']:
        col1, col2 = st.columns([1, 2])
        with col1:
            st.image(video['snippet']['thumbnails']['medium']['url'], use_column_width=True)
        with col2:
            st.subheader(video['snippet']['title'])
            st.markdown(f"**채널명:** {video['snippet']['channelTitle']}")
            st.write(video['snippet']['description'])
            video_url = f"https://www.youtube.com/watch?v={video['id']['videoId']}"
            st.markdown(f"[영상 보기]({video_url})")
            
            video_id = video['id']['videoId']
            video_title = video['snippet']['title']
            caption = video.get('caption', None)  # 저장된 자막 불러오기

            if st.button(f"📋 요약 보고서 요청", key=f"summarize_{video_id}"):
                with st.spinner("영상을 요약하는 중..."):
                    summary = summarize_video(video_id, video_title, caption)
                    st.session_state.summary = summary
        st.divider()

elif source == "뉴스":
    st.subheader(f"📰 검색된 뉴스 기사")
    for i, article in enumerate(st.session_state.search_results['news']):
        st.subheader(article['title'])
        st.markdown(f"**출처:** {article['source']['name']}")
        st.write(article['description'])
        st.markdown(f"[기사 보기]({article['url']})")
        st.divider()

# 요약 결과 표시 및 다운로드 버튼
st.markdown('<div class="fixed-footer">', unsafe_allow_html=True)
col1, col2 = st.columns([0.85, 0.15])  # 열을 비율로 분할
with col1:
    if source == "YouTube":
        st.subheader("📋 영상 요약 보고서")
    elif source == "뉴스":
        st.subheader("📋 뉴스 종합 분석 보고서")
    else:
        st.subheader("📈 재무정보 분석 보고서")
with col2:
    if st.session_state.summary:
        download_summary_file(st.session_state.summary)

if st.session_state.summary:
    st.markdown(st.session_state.summary, unsafe_allow_html=True)
else:
    if source == "YouTube":
        st.write("검색 결과에서 요약할 영상을 선택하세요.")
    elif source == "뉴스":
        st.write("뉴스 검색 결과가 없습니다.")
    else:
        st.write("재무정보 검색 결과가 없습니다.")
st.markdown('</div>', unsafe_allow_html=True)

# 주의사항 및 안내
st.sidebar.markdown("---")
st.sidebar.markdown("**안내사항:**")
st.sidebar.markdown("- 이 서비스는 Google AI Studio API, YouTube Data API, Google Search API, SERP API를 사용합니다.")
st.sidebar.markdown("- 검색 결과의 품질과 복잡도에 따라 처리 시간이 달라질 수 있습니다.")
st.sidebar.markdown("- 저작권 보호를 위해 개인적인 용도로만 사용해주세요.")
st.sidebar.markdown("- 제공되는 정보는 참고용이며, 투자 결정에 직접적으로 사용하지 마세요.")
