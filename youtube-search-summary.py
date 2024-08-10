import streamlit as st
import google.generativeai as genai
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
import os

# Streamlit 앱 설정
st.set_page_config(page_title="AI YouTube 검색 및 요약", page_icon="📺", layout="wide")

# API 키 설정
genai.configure(api_key=st.secrets["GOOGLE_AI_STUDIO_API_KEY"])
youtube = build('youtube', 'v3', developerKey=st.secrets["YOUTUBE_API_KEY"])

# 자막 가져오기 함수 (YouTube Transcript API 사용)
def get_video_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko', 'en'])
        return ' '.join([entry['text'] for entry in transcript])
    except Exception as e:
        return None

# YouTube 검색 및 자막 확인 함수
def search_videos_with_transcript(query, published_after, max_results=5):
    request = youtube.search().list(
        q=query,
        type='video',
        part='id,snippet',
        order='date',  # 최신 순으로 정렬
        publishedAfter=published_after,
        maxResults=max_results * 2  # 관련성 높은 결과를 필터링하기 위해 더 많은 결과 요청
    )
    response = request.execute()

    # 결과를 관련성 기준으로 필터링
    videos_with_transcript = []
    for item in response['items']:
        video_id = item['id']['videoId']
        if get_video_transcript(video_id):
            videos_with_transcript.append(item)
        
        if len(videos_with_transcript) == max_results:  # 자막이 있는 비디오가 max_results 개수만큼 되면 루프 종료
            break
    
    return videos_with_transcript

# 영상 요약 함수 (제목 포함)
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

# 조회 기간 선택 함수
def get_published_after(option):
    from datetime import datetime, timedelta

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
st.title("📺 AI YouTube 맞춤 검색 및 요약 서비스")
st.markdown("이 서비스는 YouTube 영상을 검색하고 AI를 이용해 요약 정보를 제공합니다. 좌측 사이드바에 검색 조건을 입력하고 영상을 찾아보세요.")

# 사이드바에 검색 조건 배치
with st.sidebar:
    st.header("검색 조건")
    keyword1 = st.text_input("첫 번째 키워드", key="keyword1")
    keyword2 = st.text_input("두 번째 키워드 (선택 사항)", key="keyword2")
    keyword3 = st.text_input("세 번째 키워드 (선택 사항)", key="keyword3")

    period = st.selectbox("조회 기간", ["모두", "최근 1일", "최근 1주일", "최근 1개월", "최근 3개월", "최근 6개월", "최근 1년"], index=1)

    search_button = st.button("검색 실행")

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
        with st.spinner("영상을 검색하고 자막을 확인하는 중..."):
            published_after = get_published_after(period)
            videos = search_videos_with_transcript(keywords, published_after)
        st.session_state.search_results = videos
        # 검색 실행 시 요약 결과 초기화
        st.session_state.summary = ""
        if not videos:
            st.warning("자막이 있는 영상을 찾을 수 없습니다. 다른 키워드로 검색해보세요.")
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
        video_url = f"https://www.youtube.com/watch?v={video['id']['videoId']}"
        st.markdown(f"[영상 보기]({video_url})")
        
        if st.button(f"요약 보고서 요청 (결과는 화면 하단에서 확인하세요.)", key=f"summarize_{video['id']['videoId']}"):
            with st.spinner("영상을 요약하는 중..."):
                summary = summarize_video(video['id']['videoId'], video['snippet']['title'])
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
    st.write("영상을 선택하고 요약 보고서 요청 버튼을 클릭하세요.")
st.markdown('</div>', unsafe_allow_html=True)

# 주의사항 및 안내
st.sidebar.markdown("---")
st.sidebar.markdown("**안내사항:**")
st.sidebar.markdown("- 이 서비스는 Google AI Studio API와 YouTube Data API를 사용합니다.")
st.sidebar.markdown("- 영상의 길이와 복잡도에 따라 처리 시간이 달라질 수 있습니다.")
st.sidebar.markdown("- 저작권 보호를 위해 개인적인 용도로만 사용해주세요.")
