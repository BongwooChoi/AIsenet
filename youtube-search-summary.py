import streamlit as st
import google.generativeai as genai
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
import os
from datetime import datetime

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
    
    return videos_with_transcript[:max_results]

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
        data=summa
