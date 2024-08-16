import streamlit as st
import google.generativeai as genai
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
import os
from datetime import datetime, timedelta
import requests
import urllib.parse

# Streamlit 앱 설정
st.set_page_config(page_title="AI 금융정보 검색 및 분석 서비스", page_icon="📈", layout="wide")

# API 키 설정
genai.configure(api_key=st.secrets["GOOGLE_AI_STUDIO_API_KEY"])
youtube = build('youtube', 'v3', developerKey=st.secrets["YOUTUBE_API_KEY"])

# 금융 도메인별 키워드 정의
FINANCE_DOMAINS = {
    "주식": ["주식", "증권", "배당주", "주가", "상장", "코스피", "코스닥", "러셀", "나스닥", "S&P500", "다우존스", "닛케이"],
    "부동산": ["부동산", "아파트", "주택", "오피스텔", "분양", "청약", "재건축", "재개발", "임대", "상가"],
    "코인": ["암호화폐", "가상화폐", "가상자산", "비트코인", "이더리움", "블록체인", "코인", "거래소", "채굴", "NFT"],
    "채권/금리/환율": ["채권", "국채", "회사채", "금리", "한국은행", "한은", "연준", "환율", "통화", "달러", "엔화", "위안화", "유로화"],
    "경제일반": ["경제", "무역", "물가", "인플레이션", "국내총생산", "GDP", "소비자물가지수", "생산자물가지수","CPI", "고용", "실업률", "수출", "소비"]
}

# 뉴스 검색 함수 (Serp API 사용)
def search_news(domain, additional_query, published_after, max_results=10):
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
def search_videos_with_transcript(domain, additional_query, published_after, max_results=10):
    try:
        keywords = " OR ".join(FINANCE_DOMAINS[domain])
        query = f"({keywords}) {additional_query}".strip()
        
        # st.write(f"검색 쿼리: {query}")  # 디버깅용 로그
        
        request = youtube.search().list(
            q=query,
            type='video',
            part='id,snippet',
            order='relevance',
            publishedAfter=published_after,
            maxResults=max_results
        )
        response = request.execute()
        
        # st.write(f"검색된 총 비디오 수: {len(response['items'])}")  # 디버깅용 로그

        videos_with_transcript = []
        for item in response['items']:
            video_id = item['id']['videoId']
            if get_video_transcript(video_id):
                videos_with_transcript.append(item)
        
        # st.write(f"자막이 있는 비디오 수: {len(videos_with_transcript)}")  # 디버깅용 로그
        
        return videos_with_transcript[:max_results], len(response['items'])
    except Exception as e:
        st.error(f"YouTube 검색 중 오류 발생: {str(e)}")
        return [], 0

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

# 뉴스 기사 종합 분석 함수
def analyze_news_articles(articles):
    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        
        # 모든 기사의 제목과 내용을 하나의 문자열로 결합
        all_articles = "\n\n".join([f"제목: {article['title']}\n내용: {article['content']}" for article in articles])
        
        prompt = f"""
다음은 특정 주제에 관한 여러 뉴스 기사의 제목과 내용입니다. 이 기사들을 종합적으로 분석하여 가독성 있는 한 페이지의 보고서를 다음 형식을 참고하여 작성해주세요:

1. 주요 이슈 요약 (3-5개의 핵심 포인트)
2. 상세 분석 (각 주요 이슈에 대한 심층 설명)
3. 다양한 관점 (기사들에서 나타난 서로 다른 의견이나 해석)
4. 시사점 및 향후 전망

보고서는 한국어로 작성해주세요. 분석 시 객관성을 유지하고, 편향된 의견을 제시하지 않도록 주의해주세요.

기사 내용:
{all_articles}
"""
        response = model.generate_content(prompt)

        if not response or not response.parts:
            feedback = response.prompt_feedback if response else "No response received."
            return f"분석 중 오류가 발생했습니다: {feedback}"

        analysis = response.text
        return analysis
    except Exception as e:
        return f"분석 중 오류가 발생했습니다: {str(e)}"

# 파일로 다운로드할 수 있는 함수
def download_summary_file(summary_text, file_name="summary.txt"):
    st.download_button(
        label="다운로드",
        data=summary_text,
        file_name=file_name,
        mime="text/plain"
    )

# 이메일로 공유하는 함수
def share_by_email(summary_text):
    st.write("이메일로 공유")
    email = st.text_input("받는 사람 이메일 주소")
    if st.button("공유하기"):
        if email:
            subject = "AI 금융정보 분석 결과"
            body = summary_text
            mailto_link = f"mailto:{email}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"
            st.markdown(f'<a href="{mailto_link}" target="_blank">이메일 열기</a>', unsafe_allow_html=True)
        else:
            st.warning("이메일 주소를 입력해주세요.")

# Streamlit 앱
st.title("📈 AI 금융정보 검색 및 분석 서비스")
st.markdown("이 서비스는 선택한 금융 도메인에 대한 YouTube 영상과 뉴스를 검색하고 AI를 이용해 분석 정보를 제공합니다. 좌측 사이드바에서 검색 조건을 선택하고 검색해보세요.")

# 사이드바에 검색 조건 배치
with st.sidebar:
    st.header("검색 조건")
    source = st.radio("검색할 소스를 선택하세요:", ("YouTube", "뉴스"))
    domain = st.selectbox("금융 도메인 선택", list(FINANCE_DOMAINS.keys()))
    additional_query = st.text_input("추가 검색어 (선택 사항)", key="additional_query")
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
    with st.spinner(f"{source}를 검색하고 있습니다..."):
        published_after = get_published_after(period)
        
        if source == "YouTube":
            # YouTube 영상 검색
            videos, total_video_results = search_videos_with_transcript(domain, additional_query, published_after)
            st.session_state.search_results = {'videos': videos, 'news': []}
            st.session_state.total_results = total_video_results
            st.session_state.summary = ""  # YouTube 검색 시 요약 초기화
        
        elif source == "뉴스":
            # 뉴스 검색 및 자동 분석
            news_articles = search_news(domain, additional_query, published_after, max_results=10)
            total_news_results = len(news_articles)
            st.session_state.search_results = {'videos': [], 'news': news_articles}
            st.session_state.total_results = total_news_results
            
            # 뉴스 기사 자동 분석
            with st.spinner("뉴스 기사를 종합 분석 중입니다..."):
                st.session_state.summary = analyze_news_articles(news_articles)
        
        if not st.session_state.total_results:
            st.warning(f"{source}에서 결과를 찾을 수 없습니다. 다른 도메인이나 검색어로 검색해보세요.")

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
        
        st.divider()

# 요약 결과 표시 및 다운로드 버튼
st.markdown('<div class="fixed-footer">', unsafe_allow_html=True)
col1, col2, col3 = st.columns([0.7, 0.15, 0.15])  # 열을 비율로 분할
with col1:
    if source == "YouTube":
        st.subheader("영상 요약 보고서")
    else:
        st.subheader("뉴스 종합 분석 보고서")
with col2:
    if st.session_state.summary:
        download_summary_file(st.session_state.summary)
with col3:
    if st.session_state.summary:
        share_by_email(st.session_state.summary)

if st.session_state.summary:
    st.markdown(f'<div class="scrollable-container">{st.session_state.summary}</div>', unsafe_allow_html=True)
else:
    if source == "YouTube":
        st.write("검색 결과에서 요약할 영상을 선택하세요.")
    else:
        st.write("뉴스 검색 결과가 없습니다.")
st.markdown('</div>', unsafe_allow_html=True)

# 주의사항 및 안내
st.sidebar.markdown("---")
st.sidebar.markdown("**안내사항:**")
st.sidebar.markdown("- 이 서비스는 Google AI Studio API, YouTube Data API, Google Search API를 사용합니다.")
st.sidebar.markdown("- 검색 결과의 품질과 복잡도에 따라 처리 시간이 달라질 수 있습니다.")
st.sidebar.markdown("- 저작권 보호를 위해 개인적인 용도로만 사용해주세요.")
st.sidebar.markdown("- 제공되는 정보는 참고용이며, 투자 결정에 직접적으로 사용하지 마세요.")
