import json
import urllib.request
import urllib.error
import streamlit as st

# --------------------------------------------------
# 1. 페이지 기본 설정 (아이패드 및 모바일 최적화)
# --------------------------------------------------
st.set_page_config(
    page_title="Biz English Daily 30",
    page_icon="💼",
    layout="centered"
)

# --------------------------------------------------
# 2. 세션 상태(State) 초기화
# --------------------------------------------------
if "word_list" not in st.session_state:
    st.session_state.word_list = []
if "current_index" not in st.session_state:
    st.session_state.current_index = 0
if "attempts" not in st.session_state:
    st.session_state.attempts = 0
if "wrong_notes" not in st.session_state:
    st.session_state.wrong_notes = []
if "is_correct" not in st.session_state:
    st.session_state.is_correct = False
if "feedback_msg" not in st.session_state:
    st.session_state.feedback_msg = None

# --------------------------------------------------
# 3. Gemini REST API 직접 호출 함수 (외부 패키지 설치 불필요)
# --------------------------------------------------
def generate_daily_words(api_key: str, count: int = 30):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    prompt = f"""
당신은 비즈니스 영어 교육 전문가입니다.
회사 실무(기획, 전략, 리소스 배분, 이메일 커뮤니케이션, 미팅 조율, 리스크 관리 등)에서 바로 사용할 수 있는 실무 비즈니스 영어 표현 {count}개를 생성해주세요.

반드시 아래 JSON 스키마를 준수하는 유효한 JSON 배열만 응답하세요. 백틱(`)이나 마크다운 없이 순수 JSON만 반환하세요:
[
  {{
    "id": 1,
    "category": "Email",
    "korean": "핵심 표현이 강조된 자연스러운 한국어 업무 상황 문장 (강조 단어는 [ ] 표시)",
    "prefix": "빈칸 앞 영어 문장",
    "answer": "빈칸에 들어갈 영어 단어 또는 구동사(소문자)",
    "suffix": "빈칸 뒤 영어 문장",
    "clue": "1차 힌트로 제공할 품사 및 뉘앙스 설명",
    "explanation": "해당 단어의 실무 뉘앙스 및 대체 표현 팁"
  }}
]
"""
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.7
        }
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            res_data = json.loads(res.read().decode("utf-8"))
            raw_text = res_data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(raw_text)
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        raise RuntimeError(f"API 오류 ({e.code}): {err_msg}")
    except Exception as e:
        raise RuntimeError(f"요청 실패: {str(e)}")

# --------------------------------------------------
# 4. API 키 자동 로딩 (Streamlit Secrets 지원)
# --------------------------------------------------
st.title("💼 Biz English Daily Study")

default_key = ""
try:
    default_key = st.secrets.get("GEMINI_API_KEY", "")
except Exception:
    default_key = ""

# --------------------------------------------------
# 5. 초기 대기 화면 (단어 생성 전)
# --------------------------------------------------
if not st.session_state.word_list:
    st.markdown("### 🚀 오늘의 학습 시작하기")
    
    if default_key:
        api_key_input = default_key
        st.success("🔒 Secrets에 등록된 Gemini API 키가 자동으로 연동되었습니다.")
    else:
        api_key_input = st.text_input("Gemini API Key를 입력하세요", type="password")

    col1, col2 = st.columns([2, 1])
    with col1:
        word_count = st.slider("학습할 단어 수", min_value=5, max_value=30, value=30, step=5)
    with col2:
        st.write("")
        st.write("")
        start_btn = st.button("단어 생성 시작", use_container_width=True)

    if start_btn:
        target_key = api_key_input.strip()
        if not target_key:
            st.error("API 키를 입력해주세요. (Settings > Secrets에 등록하면 매번 입력하지 않아도 됩니다.)")
        else:
            with st.spinner("비즈니스 실무 단어를 지능형으로 선별 중입니다... (약 5~10초 소요)"):
                try:
                    words = generate_daily_words(target_key, count=word_count)
                    st.session_state.word_list = words
                    st.session_state.current_index = 0
                    st.session_state.attempts = 0
                    st.session_state.is_correct = False
                    st.session_state.feedback_msg = None
                    st.rerun()
                except Exception as e:
                    st.error(f"생성 실패: {e}")
    st.stop()

# --------------------------------------------------
# 6. 오늘 학습 완료 화면
# --------------------------------------------------
if st.session_state.current_index >= len(st.session_state.word_list):
    st.balloons()
    st.success("🎉 오늘 목표한 단어 학습을 모두 마쳤습니다!")
    
    col_a, col_b = st.columns(2)
    col_a.metric("총 학습 단어", f"{len(st.session_state.word_list)}개")
    col_b.metric("오답 노트", f"{len(st.session_state.wrong_notes)}개")
    
    if st.session_state.wrong_notes:
        st.subheader("📝 오늘 틀린 단어 모아보기")
        for item in st.session_state.wrong_notes:
            with st.expander(f"📌 {item['answer']} ({item['category']})"):
                st.write(f"**상황:** {item['korean']}")
                st.write(f"**문맥:** {item['prefix']} **{item['answer']}
