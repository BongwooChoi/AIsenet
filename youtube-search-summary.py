import streamlit as st
import google.generativeai as genai
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
import os
from datetime import datetime, timedelta
import requests  # 뉴스 검색을 위해 사용

# Streamlit 앱 설정
st.set_page_config(page_title="AI YouTube & 뉴스 검색 및 요약", page_icon="📰", layout="wide")

# API 키 설정
genai.configure(api_key=st.secrets["GOOGLE_AI_STUDIO_API_KEY"])
youtube = build('youtube', 'v3', developerKey=st.secrets["YOUTUBE_API_KEY"])

# 뉴스 검색 함수 (Google News API 사용 예시)
def search_news(query, published_after, max_results=5):
    api_key = st.secrets["GOOGLE_NEWS_API_KEY"]
    url = f"https://newsapi.org/v2/everything?q={query}&from={published_after}&sortBy=relevance&apiKey={api_key}&pageSize={max_results}"
    response = requests.get(url)
    news_data = response.json()
    return news_data.get('articles', [])

# 자막 가져오기 함수 (YouTube Transcript API 사용)
def get_video_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko', 'en'])
        return ' '.join([entry['text'] for entry in transcript])
    except Exception as e:
        return None

# 유튜브 검색 및 최신 순 정렬 함수
def search_videos_with_transcript(query, published_after, max_results=5):
    # 관련성 높은 순으로 검색
    request = youtube.search().list(
        q=query,
        type='video',
        part='id,snippet',
        order='relevance',  # 관련성 높은 순으로 정렬
        publishedAfter=published_after,
        maxResults=max_results * 2  # 더 많은 결과를 요청해 이후 최신 순으로 필터링
    )
    response = request.execute()

    # 검색 결과를 최신 순으로 정렬
    videos_with_transcript = []
    for item in response['items']:
        video_id = item['id']['videoId']
        if get_video_transcript(video_id):
            videos_with_transcript.append(item)
    
    # 최신 순으로 정렬
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

# 파일로 다운로드할 수 있는 함수
def download_summary_file(summary_text, file_name="summary.txt"):
    st.download_button(
        label="요약 보고서 다운로드",
        data=summary_text,
        file_name=file_name,
        mime="text/plain"
    )

# Streamlit 앱
st.title("📰 AI YouTube & 뉴스 검색 및 요약 서비스")
st.markdown("이 서비스는 YouTube 영상과 뉴스를 검색하고 AI를 이용해 요약 정보를 제공합니다. 좌측 사이드바에 검색 조건을 입력하고 검색해보세요.")

# 사이드바에 검색 조건 배치
with st.sidebar:
    st.header("검색 조건")
    keyword1 = st.text_input("첫 번째 키워드", key="keyword1")
    keyword2 = st.text_input("두 번째 키워드 (선택 사항)", key="keyword2")
    keyword3 = st.text_input("세 번째 키워드 (선택 사항)", key="keyword3")

    period = st.selectbox("조회 기간", ["모두", "최근 1일", "최근 1주일", "최근 1개월", "최근 3개월", "최근 6개월", "최근 1년"], index=2)

    search_button = st.button("검색 실행")

# 검색 결과 저장용 세션 상태
if 'search_results' not in st.session_state:
    st.session_state.search_results = []
    st.session_state.total_results = 0

# 요약 결과 저장용 세션 상태
if 'summary' not in st.session_state:
    st.session_state.summary = ""

# 검색 실행
if search_button:
    keywords = " ".join(filter(None, [keyword1, keyword2, keyword3]))
    if keywords:
        with st.spinner("영상을 검색하고 자막을 확인하는 중..."):
            published_after = get_published_after(period)
            
            # YouTube 영상 검색
            videos, total_video_results = search_videos_with_transcript(keywords, published_after)
            
            # 뉴스 검색
            news_articles = search_news(keywords, published_after)
            total_news_results = len(news_articles)
            
            # 결과 통합
            st.session_state.search_results = {
                'videos': videos,
                'news': news_articles
            }
            st.session_state.total_results = total_video_results + total_news_results
            # 검색 실행 시 요약 결과 초기화
            st.session_state.summary = ""
            if not (videos or news_articles):
                st.warning("검색 결과를 찾을 수 없습니다. 다른 키워드로 검색해보세요.")
    else:
        st.warning("키워드를 입력해주세요.")

# 검색 결과 표시
st.subheader(f"검색된 총 결과: {st.session_state.total_results}개 (영상 {len(st.session_state.search_results['videos'])}개, 뉴스 {len(st.session_state.search_results['news'])}개)")
st.markdown("### YouTube 영상 결과")
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
        
        if st.button(f"요약 보고서 요청 (결과는 화면 하단에서 확인하세요.)", key=f"summarize_{video['id']['videoId']}"):
            with st.spinner("영상을 요약하는 중..."):
                summary = summarize_video(video['id']['videoId'], video['snippet']['title'])
                st.session_state.summary = summary
    st.divider()

st.markdown("### 뉴스 기사 결과")
for article in st.session_state.search_results['news']:
    st.subheader(article['title'])
    st.markdown(f"**출처:** {article['source']['name']}")
    st.write(article['description'])
    st.markdown(f"[기사 보기]({article['url']})")
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
