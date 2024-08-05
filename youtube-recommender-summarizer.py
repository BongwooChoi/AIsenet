import streamlit as st
import google.generativeai as genai
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
import os

# Streamlit 앱 설정
st.set_page_config(page_title="AI YouTube 추천 및 요약", page_icon="🎥", layout="wide")

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

        model = genai.GenerativeModel('gemini-pro')
        prompt = f"다음 YouTube 영상의 내용을 가독성 있는 한 페이지의 보고서 형태로 요약하세요. 최종 결과는 한국어로 나와야 합니다.:\n\n{transcript}"
        response = model.generate_content(prompt)
        summary = response.text

        return summary
    except Exception as e:
        return f"요약 중 오류가 발생했습니다: {str(e)}"

# Streamlit 앱 UI 코드 (이전과 동일)
# ...

# 주의사항 및 안내
st.sidebar.markdown("---")
st.sidebar.markdown("**안내사항:**")
st.sidebar.markdown("- 이 서비스는 Google AI Studio API, YouTube Data API, YouTube Transcript API를 사용합니다.")
st.sidebar.markdown("- 영상의 길이와 복잡도에 따라 처리 시간이 달라질 수 있습니다.")
st.sidebar.markdown("- 저작권 보호를 위해 개인적인 용도로만 사용해주세요.")
