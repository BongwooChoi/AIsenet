import ffmpeg
import streamlit as st
import google.generativeai as genai
from googleapiclient.discovery import build
import yt_dlp
import whisper
from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
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
openai_api_key = st.secrets["openai_api_key"]
os.environ["OPENAI_API_KEY"] = openai_api_key

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

# 영상 요약 함수
def summarize_video(youtube_url):
    try:
        # 1. YouTube 영상 다운로드
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': 'audio.%(ext)s'
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([youtube_url])

        # 2. 음성 인식 (Whisper)
        model = whisper.load_model("tiny")
        result = model.transcribe("audio.mp3")
        transcription = result["text"]

        # 3. 텍스트 요약 (GPT-4o-mini)
        chat = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)
        messages = [
            SystemMessage(content="당신은 YouTube 영상을 시청하고 내용을 정리해서 알려주는 Assistant입니다."),
            HumanMessage(content=f"아래 내용을 가독성 있는 한 페이지의 보고서 형태로 요약하세요. 최종결과는 한국어로 나와야 합니다.:\n\n{transcription}")
        ]
        summary = chat(messages).content

        return summary
    except Exception as e:
        return f"요약 중 오류가 발생했습니다: {str(e)}"

# Streamlit 앱
st.title("🎥 AI YouTube 영상 추천 및 요약")

# 키워드 입력
col1, col2, col3 = st.columns(3)
with col1:
    keyword1 = st.text_input("첫 번째 키워드", key="keyword1")
with col2:
    keyword2 = st.text_input("두 번째 키워드 (선택 사항)", key="keyword2")
with col3:
    keyword3 = st.text_input("세 번째 키워드 (선택 사항)", key="keyword3")

# 정렬 기준과 재생 시간 필터
col4, col5 = st.columns(2)
with col4:
    order = st.selectbox("정렬 기준", ["관련성", "조회수", "날짜"], index=0)
with col5:
    duration = st.selectbox("재생 시간 필터", ["모두", "짧은 동영상 (< 5분)", "중간 길이 동영상 (5~20분)", "긴 동영상 (> 20분)"], index=0)

# 매개변수 변환
order_dict = {"관련성": "relevance", "조회수": "viewCount", "날짜": "date"}
duration_dict = {"모두": None, "짧은 동영상 (< 5분)": "short", "중간 길이 동영상 (5~20분)": "medium", "긴 동영상 (> 20분)": "long"}

# 키워드 검색
keywords = " ".join(filter(None, [keyword1, keyword2, keyword3]))
if keywords:
    videos = search_videos(keywords, order=order_dict[order], duration=duration_dict[duration])
    if videos:
        st.subheader("검색 결과")
        for video in videos:
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
                
                # 요약하기 버튼 추가
                if st.button(f"요약하기", key=f"summarize_{video['id']['videoId']}"):
                    with st.spinner("영상을 요약하는 중..."):
                        summary = summarize_video(video_url)
                        st.subheader("영상 요약")
                        # 스크롤 가능한 컨테이너에 요약 내용 표시
                        st.markdown(f'<div class="scrollable-container">{summary}</div>', unsafe_allow_html=True)
            st.divider()
    else:
        st.warning("검색 결과가 없습니다.")

# 주의사항 및 안내
st.markdown("---")
st.markdown("**안내사항:**")
st.markdown("- 이 서비스는 Google AI Studio API, YouTube Data API, OpenAI의 Whisper와 GPT-4o-mini를 사용합니다.")
st.markdown("- 영상의 길이와 복잡도에 따라 처리 시간이 달라질 수 있습니다.")
st.markdown("- 저작권 보호를 위해 개인적인 용도로만 사용해주세요.")
