import streamlit as st
import google.generativeai as genai
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
import os
from datetime import datetime, timedelta
import requests

# Streamlit 앱 설정
st.set_page_config(page_title="AI YouTube & 뉴스 검색 및 요약", page_icon="📰", layout="wide")

# API 키 설정
genai.configure(api_key=st.secrets["GOOGLE_AI_STUDIO_API_KEY"])
youtube = build('youtube', 'v3', developerKey=st.secrets["YOUTUBE_API_KEY"])

# 뉴스 검색 함수 (Serp API 사용)
def search_news(query, published_after, max_results=10):
    api_key = st.secrets["SERP_API_KEY"]
    url = f"https://serpapi.com/search.json?q={query}&tbm=nws&api_key={api_key}&num={max_results * 2}&sort=date"
    
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

# 자막 가져오기 함수 (YouTube Transcript API 사용)
def get_video_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko', 'en'])
        return ' '.join([entry['text'] for entry in transcript])
    except Exception as e:
        return None

# 유튜브 검색 및 최신 순 정렬 함수
def search_videos_with_transcript(query, published_after, max_results=5):
    request = youtube.search().list(
        q=query,
        type='video',
        part='id,snippet',
        order='relevance',
        publishedAfter=published_after,
        maxResults=max_results * 2
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

# 뉴스 기사 요약 및 분석 함수
def summarize_and_analyze_article(article):
    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        prompt = f"""
다음 뉴스 기사의 제목과 내용을 요약하고, 해당 내용이 투자에 미치는 영향을 긍정적 또는 부정적으로 분석하세요. 
분석 결과와 함께 그 이유를 설명하고, 이 내용을 바탕으로 추천 여부와 추천 사유를 포함하여 답변하세요. 
또한, 요약 마지막에 원문의 언어(한국어 또는 영어)를 명시해 주세요.

제목: {article['title']}

내용: {article['content']}
"""
        response = model.generate_content(prompt)

        if not response or not response.parts:
            feedback = response.prompt_feedback if response else "No response received."
            return {
                "summary": f"요약 중 오류가 발생했습니다: {feedback}",
                "recommendation": "분석 불가",
                "tag": "불명확",
                "importance": "★"
            }

        summary = response.text
        # gemini-1.5-pro로부터 받은 추천 사유와 태그를 포함한 요약 반환
        return {
            "summary": summary,
            "recommendation": summary.split("\n")[-3],  # 추천 사유가 포함된 부분 추출
            "tag": summary.split("\n")[-2],  # 긍정/부정 태그 추출
            "importance": summary.split("\n")[-1]  # 중요도 추출
        }
    except Exception as e:
        return {
            "summary": f"요약 중 오류가 발생했습니다: {str(e)}",
            "recommendation": "분석 불가",
            "tag": "불명확",
            "importance": "★"
        }

# 파일로 다운로드할 수 있는 함수
def download_summary_file(summary_text, file_name="summary.txt"):
    st.download_button(
        label="다운로드",
        data=summary_text,
        file_name=file_name,
        mime="text/plain"
    )

# Streamlit 앱
st.title("📰 AI YouTube & 뉴스 검색 및 요약 서비스")
st.markdown("이 서비스는 YouTube 영상과 뉴스(한국어 및 영어)를 검색하고 AI를 이용해 요약 정보를 제공합니다. 좌측 사이드바에 검색 조건을 입력하고 검색해보세요.")

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
                news_articles = search_news(keywords, published_after, max_results=20)
                total_news_results = len(news_articles)
                st.session_state.search_results = {'videos': [], 'news': news_articles}
                st.session_state.total_results = total_news_results
            
            # 검색된 모든 결과에 대해 요약 및 추천 분석 실행
            for i, article in enumerate(st.session_state.search_results['news']):
                st.session_state.search_results['news'][i].update(summarize_and_analyze_article(article))
            for i, video in enumerate(st.session_state.search_results['videos']):
                st.session_state.search_results['videos'][i].update(summarize_and_analyze_article(video['snippet']))
            
            # 검색 실행 시 요약 결과 초기화
            st.session_state.summary = ""
            if not st.session_state.total_results:
                st.warning(f"{source}에서 결과를 찾을 수 없습니다. 다른 키워드로 검색해보세요.")
    else:
        st.warning("키워드를 입력해주세요.")

# 검색 결과 표시 및 추천 콘텐츠 선정
if source == "YouTube":
    st.subheader(f"검색된 총 YouTube 영상: {st.session_state.total_results}개")
    recommended_contents = []
    
    for video in st.session_state.search_results['videos']:
        col1, col2 = st.columns([1, 2])
        with col1:
            st.image(video['snippet']['thumbnails']['medium']['url'], use_column_width=True)
        with col2:
            st.subheader(video['snippet']['title'])
            st.markdown(f"**채널명:** {video['snippet']['channelTitle']}")
            st.write(video['snippet']['description'])
            
            if 'recommendation' in video:
                st.markdown(f"**추천 사유:** {video['recommendation']}")
                st.markdown(f"**태그:** {video['tag']}, **중요도:** {video['importance']}")
                
            video_url = f"https://www.youtube.com/watch?v={video['id']['videoId']}"
            st.markdown(f"[영상 보기]({video_url})")
        st.divider()

elif source == "뉴스":
    st.subheader(f"검색된 총 뉴스 기사: {st.session_state.total_results}개")
    recommended_contents = []
    
    for i, article in enumerate(st.session_state.search_results['news']):
        st.subheader(article['title'])
        st.markdown(f"**출처:** {article['source']['name']}")
        st.write(article['description'])
        
        if 'recommendation' in article:
            st.markdown(f"**추천 사유:** {article['recommendation']}")
            st.markdown(f"**태그:** {article['tag']}, **중요도:** {article['importance']}")
        
        st.markdown(f"[기사 보기]({article['url']})")
        st.divider()

# 추천 콘텐츠를 중요도에 따라 정렬하고 상위 5개 표시
recommended_contents.sort(key=lambda x: x["importance"], reverse=True)
top_recommendations = recommended_contents[:5]

st.subheader("투자에 도움이 될 만한 추천 콘텐츠 TOP 5")
for i, recommendation in enumerate(top_recommendations):
    st.write(f"**{i+1}. 요약 내용:** {recommendation['summary']}")
    st.write(f"**추천 사유:** {recommendation['recommendation']}")
    st.write(f"**태그:** {recommendation['tag']}, **중요도:** {recommendation['importance']}")
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
