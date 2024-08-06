import streamlit as st
import google.generativeai as genai
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
import os

# Streamlit 앱 설정
st.set_page_config(page_title="AI YouTube 추천 및 요약", page_icon="📺", layout="wide")

# CSS를 사용하여 스크롤 가능한 컨테이너 스타일 정의
st.markdown("""
<style>
.scrollable-container {
    height: 300px;
    overflow-y: auto;
    border: 1px solid #ddd;
    padding: 10px;
    border-radius: 5px;
}
</style>
""", unsafe_allow_html=True)

# API 키 설정
genai.configure(api_key=st.secrets["GOOGLE_AI_STUDIO_API_KEY"])
youtube = build('youtube', 'v3', developerKey=st.secrets["YOUTUBE_API_KEY"])

# YouTube 검색 함수
def search_videos(query, order='relevance', duration=None, max_results=5):
    request = youtube.search().list(
        q=query,
        type='video',
        part='id,snippet',
        order=order,
        videoDuration=duration,
        maxResults=max_results
    )
    response = request.execute()
    return response['items']

# AI 추천 이유 생성 함수
def get_ai_recommendation(video_title, video_description):
    model = genai.GenerativeModel('gemini-pro')
    prompt = f"다음 YouTube 영상에 대한 추천 이유를 한국어로 간단히 설명해주세요:\n제목: {video_title}\n설명: {video_description}"
    response = model.generate_content(prompt)
    return response.text

# 자막 가져오기 함수 (YouTube Transcript API 사용)
def get_video_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko', 'en'])
        return ' '.join([entry['text'] for entry in transcript])
    except Exception as e:
        st.error(f"자막을 가져오는 중 오류 발생: {str(e)}")
        return None

# 영상 요약 함수
def summarize_video(video_id):
    try:
        transcript = get_video_transcript(video_id)
        if not transcript:
            return "자막을 가져올 수 없어 요약할 수 없습니다."

        model = genai.GenerativeModel('gemini-1.5-pro')
        prompt = f"다음 YouTube 영상의 내용을 가독성 있는 한 페이지의 보고서 형태로 요약하세요. 최종 결과는 한국어로 나와야 합니다.:\n\n{transcript}"
        response = model.generate_content(prompt)
        summary = response.text

        return summary
    except Exception as e:
        return f"요약 중 오류가 발생했습니다: {str(e)}"

# Streamlit 앱
st.title("📺 AI YouTube 영상 추천 및 요약")
st.markdown("이 서비스는 YouTube 영상을 검색하고 AI를 이용해 추천 이유와 요약을 제공합니다. 좌측 사이드바에 검색 조건을 입력하고 영상을 찾아보세요.")

# 사이드바에 검색 조건 배치
with st.sidebar:
    st.header("검색 조건")
    keyword1 = st.text_input("첫 번째 키워드", key="keyword1")
    keyword2 = st.text_input("두 번째 키워드 (선택 사항)", key="keyword2")
    keyword3 = st.text_input("세 번째 키워드 (선택 사항)", key="keyword3")

    order = st.selectbox("정렬 기준", ["관련성", "조회수", "날짜"], index=0)
    duration = st.selectbox("재생 시간 필터", ["모두", "짧은 동영상 (< 5분)", "중간 길이 동영상 (5~20분)", "긴 동영상 (> 20분)"], index=0)

    search_button = st.button("검색 실행")

# 매개변수 변환
order_dict = {"관련성": "relevance", "조회수": "viewCount", "날짜": "date"}
duration_dict = {"모두": None, "짧은 동영상 (< 5분)": "short", "중간 길이 동영상 (5~20분)": "medium", "긴 동영상 (> 20분)": "long"}

# 검색 결과 저장용 세션 상태
if 'search_results' not in st.session_state:
    st.session_state.search_results = []

# 요약 결과 저장용 세션 상태
if 'summary' not in st.session_state:
    st.session_state.summary = ""

# 검색 실행
if search_button:
    keywords = " ".join(filter(None, [keyword1, keyword2, keyword3]))
    if keywords:
        videos = search_videos(keywords, order=order_dict[order], duration=duration_dict[duration])
        st.session_state.search_results = videos
    else:
        st.warning("키워드를 입력해주세요.")

# 검색 결과 표시
st.subheader("검색 결과")
for video in st.session_state.search_results:
    col1, col2 = st.columns([1, 2])
    with col1:
        st.image(video['snippet']['thumbnails']['medium']['url'], use_column_width=True)
    with col2:
        st.subheader(video['snippet']['title'])
        st.write(video['snippet']['description'])
        recommendation = get_ai_recommendation(video['snippet']['title'], video['snippet']['description'])
        st.info("AI 추천 이유: " + recommendation)
        video_url = f"https://www.youtube.com/watch?v={video['id']['videoId']}"
        st.markdown(f"[영상 보기]({video_url})")
        
        if st.button(f"내용 요약하기 (요약 결과는 화면 하단에서 확인하세요.)", key=f"summarize_{video['id']['videoId']}"):
            with st.spinner("영상을 요약하는 중..."):
                summary = summarize_video(video['id']['videoId'])
                st.session_state.summary = summary
    st.divider()

# 요약 결과 표시
st.subheader("영상 요약")
if st.session_state.summary:
    st.markdown(f'<div class="scrollable-container">{st.session_state.summary}</div>', unsafe_allow_html=True)
else:
    st.write("영상을 선택하고 요약하기 버튼을 클릭하세요.")

# 주의사항 및 안내
st.sidebar.markdown("---")
st.sidebar.markdown("**안내사항:**")
st.sidebar.markdown("- 이 서비스는 Google AI Studio API와 YouTube Data API를 사용합니다.")
st.sidebar.markdown("- 영상의 길이와 복잡도에 따라 처리 시간이 달라질 수 있습니다.")
st.sidebar.markdown("- 저작권 보호를 위해 개인적인 용도로만 사용해주세요.")
