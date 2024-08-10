import streamlit as st
import google.generativeai as genai
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
import os
import time
from datetime import datetime, timedelta
import requests
import yfinance as yf
import threading

# API 키 설정
genai.configure(api_key=st.secrets["GOOGLE_AI_STUDIO_API_KEY"])
youtube = build('youtube', 'v3', developerKey=st.secrets["YOUTUBE_API_KEY"])

# 지수 정보를 가져오는 함수
def get_latest_index():
    # Yahoo Finance에서 지수 데이터 가져오기
    sp500 = yf.Ticker('^GSPC').history(period='1d')['Close'][0]
    nasdaq = yf.Ticker('^IXIC').history(period='1d')['Close'][0]
    dowjones = yf.Ticker('^DJI').history(period='1d')['Close'][0]
    kospi = yf.Ticker('^KS11').history(period='1d')['Close'][0]
    kosdaq = yf.Ticker('^KQ11').history(period='1d')['Close'][0]
    
    index_info = {
        'S&P 500': f"{sp500:.2f}",
        'Nasdaq': f"{nasdaq:.2f}",
        'Dow Jones': f"{dowjones:.2f}",
        'KOSPI': f"{kospi:.2f}",
        'KOSDAQ': f"{kosdaq:.2f}"
    }
    return index_info

# 뉴스 검색 함수 (Serp API 사용)
def search_news(query, published_after, max_results=10):
    api_key = st.secrets["SERP_API_KEY"]
    url = f"https://serpapi.com/search.json?q={query}&tbm=nws&api_key={api_key}&num={max_results}&sort=date"
    
    response = requests.get(url)
    news_data = response.json()
    articles = news_data.get('news_results', [])
    
    # 중복 제거 (URL 기준)
    unique_articles = []
    seen_urls = set()
    for article in articles:
        if article['link'] not in seen_urls:
            unique_articles.append({
                'title': article.get('title', ''),
                'source': {'name': article.get('source', '')},
                'description': article.get('snippet', ''),
                'url': article.get('link', ''),
                'content': article.get('snippet', '')  # Serp API에는 content가 없으므로 snippet으로 대체
            })
            seen_urls.add(article['link'])
        if len(unique_articles) == max_results:
            break
    
    return unique_articles

# 유튜브 검색 및 최신 순 정렬 함수
def search_videos_with_transcript(query, published_after, max_results=10):
    request = youtube.search().list(
        q=query,
        type='video',
        part='id,snippet',
        order='relevance',
        publishedAfter=published_after,
        maxResults=max_results
    )
    response = request.execute()

    videos_with_transcript = []
    for item in response['items']:
        video_id = item['id']['videoId']
        if get_video_transcript(video_id):
            videos_with_transcript.append(item)
    
    videos_with_transcript.sort(key=lambda x: x['snippet']['publishedAt'], reverse=True)
    
    return videos_with_transcript[:max_results], len(response['items'])


# 조회 기간 선택 함수
def get_published_after(option):
    today = datetime.utcnow()
    if option == "최근 1일":
        return (today - timedelta(days=1)).isoformat("T") + "Z"
    elif option == "최근 1주일":
        return (today - timedelta(weeks=1)).isoformat("T") + "Z"
    elif option == "최근 1개월":
        return (today - timedelta(weeks=4)).isoformat("T") + "Z"
    elif option == "최근 3개월":
        return (today - timedelta(weeks=12)).isoformat("T") + "Z"
    elif option == "최근 6개월":
        return (today - timedelta(weeks=24)).isoformat("T") + "Z"
    elif option == "최근 1년":
        return (today - timedelta(weeks=52)).isoformat("T") + "Z"
    else:
        return None  # 이 경우 조회 기간 필터를 사용하지 않음

# 자막 가져오기 함수 (YouTube Transcript API 사용)
def get_video_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko', 'en'])
        return ' '.join([entry['text'] for entry in transcript])
    except Exception as e:
        return None

# YouTube 영상 요약 함수
def summarize_video(video_id, video_title):
    try:
        transcript = get_video_transcript(video_id)
        if not transcript:
            return "자막을 가져올 수 없어 요약할 수 없습니다."

        model = genai.GenerativeModel('gemini-1.5-pro')
        prompt = f"다음 YouTube 영상의 제목과 내용을 가독성 있는 한 페이지의 보고서 형태로 요약하세요. 최종 결과는 한국어로 나와야 합니다.:\n\n제목: {video_title}\n\n{transcript}"
        response = model.generate_content(prompt)

        if not response or not response.parts:
            feedback = response.prompt_feedback if response else "No response received."
            return f"요약 중 오류가 발생했습니다: {feedback}"

        summary = response.text
        return summary
    except Exception as e:
        return f"요약 중 오류가 발생했습니다: {str(e)}"

# 뉴스 기사 요약 함수
def summarize_news_article(article):
    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        prompt = f"""
다음 뉴스 기사의 제목과 내용을 가독성 있는 한 페이지의 보고서 형태로 요약하세요. 
원문이 영어인 경우에도 최종 결과는 반드시 한국어로 작성해야 합니다.
또한, 요약 마지막에 원문의 언어(한국어 또는 영어)를 명시해 주세요.

제목: {article['title']}

내용: {article['content']}
"""
        response = model.generate_content(prompt)

        if not response or not response.parts:
            feedback = response.prompt_feedback if response else "No response received."
            return f"요약 중 오류가 발생했습니다: {feedback}"

        summary = response.text
        return summary
    except Exception as e:
        return f"요약 중 오류가 발생했습니다: {str(e)}"

# 파일로 다운로드할 수 있는 함수
def download_summary_file(summary_text, file_name="summary.txt"):
    st.download_button(
        label="다운로드",
        data=summary_text,
        file_name=file_name,
        mime="text/plain"
    )

# Streamlit 앱 설정
st.set_page_config(page_title="AI YouTube & 뉴스 검색 및 요약", page_icon="📰", layout="wide")

# Streamlit 앱
st.title("📰 AI YouTube & 뉴스 검색 및 요약 서비스")
st.markdown("이 서비스는 YouTube 영상과 뉴스(한국어 및 영어)를 검색하고 AI를 이용해 요약 정보를 제공합니다. 좌측 사이드바에 검색 조건을 입력하고 검색해보세요.")

index_display = st.empty()
def update_index_info():
    while True:
        latest_index = get_latest_index()
        index_display.markdown(f"""
        **📈 최신 지수 정보:**
        - **S&P 500:** {latest_index['S&P 500']} 
        - **Nasdaq:** {latest_index['Nasdaq']} 
        - **Dow Jones:** {latest_index['Dow Jones']}
        - **KOSPI:** {latest_index['KOSPI']}
        - **KOSDAQ:** {latest_index['KOSDAQ']}
        """, unsafe_allow_html=True)
        time.sleep(60)  # 1분마다 업데이트

# 지수 정보 업데이트 스레드 시작
import threading
threading.Thread(target=update_index_info, daemon=True).start()

# 사이드바에 검색 조건 배치
with st.sidebar:
    st.header("검색 조건")
    source = st.radio("검색할 소스를 선택하세요:", ("YouTube", "뉴스"))
    keyword1 = st.text_input("첫 번째 키워드", key="keyword1")
    keyword2 = st.text_input("두 번째 키워드 (선택 사항)", key="keyword2")
    keyword3 = st.text_input("세 번째 키워드 (선택 사항)", key="keyword3")

    period = st.selectbox("조회 기간", ["모두", "최근 1일", "최근 1주일", "최근 1개월", "최근 3개월", "최근 6개월", "최근 1년"], index=2)

    search_button = st.button("검색 실행")

# 검색 결과 저장용 세션 상태
if 'search_results' not in st.session_state:
    st.session_state.search_results = {'videos': [], 'news': []}
    st.session_state.total_results = 0

# 요약 결과 저장용 세션 상태
if 'summary' not in st.session_state:
    st.session_state.summary = ""

# 검색 실행
if search_button:
    keywords = " ".join(filter(None, [keyword1, keyword2, keyword3]))
    if keywords:
        with st.spinner(f"{source}를 검색하고 있습니다..."):
            published_after = get_published_after(period)
            
            if source == "YouTube":
                # YouTube 영상 검색
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

# 검색 결과 표시
if source == "YouTube":
    st.subheader(f"검색된 총 YouTube 영상: {st.session_state.total_results}개")
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
            if st.button(f"요약 보고서 요청 (결과는 화면 하단에서 확인하세요.)", key=f"summarize_{video_id}"):
                with st.spinner("영상을 요약하는 중..."):
                    summary = summarize_video(video_id, video_title)
                    st.session_state.summary = summary
        st.divider()

elif source == "뉴스":
    st.subheader(f"검색된 총 뉴스 기사: {st.session_state.total_results}개")
    for i, article in enumerate(st.session_state.search_results['news']):
        st.subheader(article['title'])
        st.markdown(f"**출처:** {article['source']['name']}")
        st.write(article['description'])
        st.markdown(f"[기사 보기]({article['url']})")
        
        if st.button(f"요약 보고서 요청 (결과는 화면 하단에서 확인하세요.)", key=f"summarize_news_{i}"):
            with st.spinner("기사를 요약하는 중..."):
                summary = summarize_news_article(article)
                st.session_state.summary = summary
        
        st.divider()

# 요약 결과 표시 및 다운로드 버튼
st.markdown('<div class="fixed-footer">', unsafe_allow_html=True)
col1, col2 = st.columns([0.85, 0.15])  # 열을 비율로 분할
with col1:
    st.subheader("요약 보고서")
with col2:
    if st.session_state.summary:
        download_summary_file(st.session_state.summary)

if st.session_state.summary:
    st.markdown(f'<div class="scrollable-container">{st.session_state.summary}</div>', unsafe_allow_html=True)
else:
    st.write("검색 결과에서 요약할 항목을 선택하세요.")
st.markdown('</div>', unsafe_allow_html=True)

# 주의사항 및 안내
st.sidebar.markdown("---")
st.sidebar.markdown("**안내사항:**")
st.sidebar.markdown("- 이 서비스는 Google AI Studio API, YouTube Data API, Google News API를 사용합니다.")
st.sidebar.markdown("- 검색 결과의 품질과 복잡도에 따라 처리 시간이 달라질 수 있습니다.")
st.sidebar.markdown("- 저작권 보호를 위해 개인적인 용도로만 사용해주세요.")
