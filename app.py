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
# 3. Gemini REST API 직접 호출 함수 (404 수정 및 타임아웃 확장)
# --------------------------------------------------
def generate_daily_words(api_key: str, count: int = 30):
    # v1 엔드포인트와 지원 모델명 적용
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    prompt = f"""
당신은 비즈니스 영어 교육 전문가입니다.
회사 실무(기획, 전략, 리소스 배분, 이메일 커뮤니케이션, 미팅 조율, 리스크 관리 등)에서 바로 사용할 수 있는 실무 비즈니스 영어 표현 {count}개를 생성해주세요.

반드시 아래 JSON 스키마를 준수하는 유효한 JSON 배열만 응답하세요. 마크다운(백틱) 없이 순수 JSON만 반환하세요:
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
        # 30개 생성을 위해 타임아웃을 60초로 연장
        with urllib.request.urlopen(req, timeout=60) as res:
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
                st.write(f"**문맥:** {item['prefix']} **{item['answer']}** {item['suffix']}")
                st.caption(item['explanation'])

    if st.button("처음부터 다시 학습하기", use_container_width=True):
        st.session_state.current_index = 0
        st.session_state.attempts = 0
        st.session_state.is_correct = False
        st.session_state.feedback_msg = None
        st.rerun()
    st.stop()

# --------------------------------------------------
# 7. 단어 퀴즈 화면 (말해보카 방식)
# --------------------------------------------------
curr = st.session_state.word_list[st.session_state.current_index]
total = len(st.session_state.word_list)

# 상단 진행 바
st.progress((st.session_state.current_index) / total)
c_left, c_right = st.columns([1, 1])
c_left.markdown(f"**분야:** `{curr['category']}`")
c_right.markdown(f"<div style='text-align: right; color: #64748b;'>{st.session_state.current_index + 1} / {total}</div>", unsafe_allow_html=True)

# 한국어 문맥 제시
st.info(f"💡 {curr['korean']}")

# 글자 수 슬롯 힌트 (0~1회 오답: 전체 빈칸 / 2회: 첫 글자 / 3회: 두 번째 글자까지)
ans = curr["answer"].strip()
attempts = st.session_state.attempts

def make_slot(target_word, attempt_count):
    tokens = target_word.split(" ")
    res = []
    for token in tokens:
        if attempt_count <= 1:
            res.append(" ".join(["_"] * len(token)))
        elif attempt_count == 2:
            first = token[0]
            rest = " ".join(["_"] * (len(token) - 1)) if len(token) > 1 else ""
            res.append(f"{first} {rest}".strip())
        else:
            first_two = token[:2]
            rest = " ".join(["_"] * (len(token) - 2)) if len(token) > 2 else ""
            res.append(f"{first_two[0]} {first_two[1:]} {rest}".strip())
    return "   ".join(res)

slot_display = make_slot(ans, attempts)

# 빈칸 문장 카드
st.markdown(
    f"""
    <div style="background-color: #f8fafc; padding: 22px; border-radius: 12px; border: 1px solid #e2e8f0; font-size: 19px; line-height: 1.6; margin: 15px 0;">
        {curr['prefix']} <strong style="color: #2563eb; letter-spacing: 2px;">[ {slot_display} ]</strong> {curr['suffix']}
    </div>
    """,
    unsafe_allow_html=True
)

# 오답 기록 함수
def record_wrong():
    if not any(item['id'] == curr['id'] for item in st.session_state.wrong_notes):
        st.session_state.wrong_notes.append(curr)

# 정답 판별
def check_answer(user_input: str):
    clean_input = user_input.strip().lower()
    if clean_input == ans.lower():
        st.session_state.is_correct = True
        st.session_state.feedback_msg = ("correct", f"🎉 **정답입니다!**\n\n📌 **실무 팁:** {curr['explanation']}")
    else:
        st.session_state.attempts += 1
        record_wrong()
        if st.session_state.attempts == 1:
            st.session_state.feedback_msg = ("hint", f"❌ **다시 시도해보세요!**\n\n💡 **1차 힌트:** {curr['clue']}")
        elif st.session_state.attempts == 2:
            st.session_state.feedback_msg = ("hint", f"❌ **첫 글자 힌트**가 열렸습니다! 위 빈칸을 확인하세요.")
        else:
            st.session_state.feedback_msg = ("hint", f"❌ **두 번째 글자 힌트**가 열렸습니다! 앞 두 글자를 참고하세요.")

# 모름(패스) 처리
def pass_question():
    st.session_state.attempts += 1
    record_wrong()
    if st.session_state.attempts == 1:
        st.session_state.feedback_msg = ("hint", f"💡 **1차 힌트:** {curr['clue']}")
    elif st.session_state.attempts == 2:
        st.session_state.feedback_msg = ("hint", f"💡 **첫 글자 힌트**가 열렸습니다!")
    else:
        st.session_state.feedback_msg = ("hint", f"💡 정답은 **{curr['answer']}** 였습니다.")
        st.session_state.is_correct = True

# 입력 폼
if not st.session_state.is_correct:
    with st.form("quiz_input_form", clear_on_submit=False):
        user_val = st.text_input("영어 단어 입력", placeholder="소문자로 입력 후 확인", label_visibility="collapsed")
        b1, b2 = st.columns([3, 1])
        with b1:
            sub = st.form_submit_button("확인 (제출)", use_container_width=True)
        with b2:
            skip = st.form_submit_button("모름 (힌트)", use_container_width=True)
            
        if sub and user_val:
            check_answer(user_val)
            st.rerun()
        elif skip:
            pass_question()
            st.rerun()

# 피드백 메시지 박스
if st.session_state.feedback_msg:
    f_type, msg = st.session_state.feedback_msg
    if f_type == "correct":
        st.success(msg)
    else:
        st.warning(msg)

# 정답 후 다음 문제 버튼
if st.session_state.is_correct:
    if st.button("다음 문제로 이동 ➡️", use_container_width=True):
        st.session_state.current_index += 1
        st.session_state.attempts = 0
        st.session_state.is_correct = False
        st.session_state.feedback_msg = None
        st.rerun()
