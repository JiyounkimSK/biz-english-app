import json
import time
import urllib.request
import urllib.error
import streamlit as st

# --------------------------------------------------
# 1. 페이지 설정
# --------------------------------------------------
st.set_page_config(
    page_title="Biz English Daily 30",
    page_icon="💼",
    layout="centered"
)

# --------------------------------------------------
# 2. 세션 상태 초기화
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
# 3. Gemini REST API 생성 함수 (재시도 & 폴백 내장)
# --------------------------------------------------
def generate_daily_words(api_key: str, count: int = 30):
    models_to_try = [
        "gemini-3.8-flash",
        "gemini-3.8-pro",
        "gemini-3.5-flash",
        "gemini-3.0-flash"
    ]
    
    prompt = f"""
당신은 비즈니스 영어 교육 전문가입니다.
회사 실무(기획, 전략, 리소스 배분, 이메일 커뮤니케이션, 미팅 조율, 리스크 관리 등)에서 바로 사용할 수 있는 완결된 전체 문장 {count}개를 생성해주세요.

반드시 다른 설명 없이 순수 JSON 배열([ ... ])만 반환하세요:
[
  {{
    "id": 1,
    "category": "Email",
    "korean_full": "앞서 논의된 대로, 우리는 다음 단계로 [진행(착수)]할 예정입니다.",
    "prefix": "As discussed earlier, we will",
    "answer": "proceed",
    "suffix": "with the next phase.",
    "clue": "동사 / 공식적인 자리에서 '앞으로 나아가다'",
    "explanation": "'start'나 'go ahead' 대신 공식 이메일에서 주로 사용됩니다."
  }}
]
"""
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    
    last_err = ""
    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        
        for _ in range(2):
            try:
                with urllib.request.urlopen(req, timeout=60) as res:
                    res_data = json.loads(res.read().decode("utf-8"))
                    raw_text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    
                    if raw_text.startswith("```"):
                        raw_text = raw_text.split("\n", 1)[1]
                    if raw_text.endswith("```"):
                        raw_text = raw_text.rsplit("\n", 1)[0]
                    raw_text = raw_text.strip()
                    
                    return json.loads(raw_text)
            except urllib.error.HTTPError as e:
                last_err = e.read().decode("utf-8")
                if e.code in [503, 429]:
                    time.sleep(1.5)
                    continue
                elif e.code == 404:
                    break
                else:
                    raise RuntimeError(f"API 오류 ({e.code}): {last_err}")
            except Exception as e:
                last_err = str(e)
                time.sleep(1.0)
                continue

    raise RuntimeError(f"단어 생성 요청 실패: {last_err}")

# --------------------------------------------------
# 4. 메인 화면 구성
# --------------------------------------------------
st.title("💼 Biz English Daily Study")

default_key = ""
try:
    default_key = st.secrets.get("GEMINI_API_KEY", "")
except Exception:
    default_key = ""

# 시작 전 대기 화면
if not st.session_state.word_list:
    st.markdown("### 🚀 오늘의 학습 시작하기")
    
    if default_key:
        api_key_input = default_key
        st.success("🔒 Secrets의 API 키가 자동으로 연동되었습니다.")
    else:
        api_key_input = st.text_input("Gemini API Key를 입력하세요", type="password")

    col1, col2 = st.columns([2, 1])
    with col1:
        word_count = st.slider("학습할 문장 수", min_value=5, max_value=30, value=30, step=5)
    with col2:
        st.write("")
        st.write("")
        start_btn = st.button("문장 생성 시작", use_container_width=True)

    if start_btn:
        target_key = api_key_input.strip()
        if not target_key:
            st.error("API 키를 먼저 입력해주세요.")
        else:
            with st.spinner("비즈니스 실무 문장을 생성 중입니다..."):
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
# 5. 전체 완료 화면
# --------------------------------------------------
if st.session_state.current_index >= len(st.session_state.word_list):
    st.balloons()
    st.success("🎉 오늘 목표한 문장 학습을 모두 마쳤습니다!")
    
    col_a, col_b = st.columns(2)
    col_a.metric("총 학습 문장", f"{len(st.session_state.word_list)}개")
    col_b.metric("오답 노트", f"{len(st.session_state.wrong_notes)}개")
    
    if st.session_state.wrong_notes:
        st.subheader("📝 오늘 틀린 문장 복습하기")
        for item in st.session_state.wrong_notes:
            with st.expander(f"📌 {item['answer']} ({item['category']})"):
                st.write(f"**한국어:** {item.get('korean_full', item.get('korean', ''))}")
                st.write(f"**완성 문장:** {item['prefix']} **{item['answer']}** {item['suffix']}")
                st.caption(item['explanation'])

    if st.button("처음부터 다시 학습하기", use_container_width=True):
        st.session_state.current_index = 0
        st.session_state.attempts = 0
        st.session_state.is_correct = False
        st.session_state.feedback_msg = None
        st.rerun()
    st.stop()

# --------------------------------------------------
# 6. 문답 퀴즈 화면 (Full Sentence + 띄어쓰기 슬롯)
# --------------------------------------------------
curr = st.session_state.word_list[st.session_state.current_index]
total = len(st.session_state.word_list)

# 상단 진행 바 & 카테고리
st.progress((st.session_state.current_index) / total)
c_left, c_right = st.columns([1, 1])
c_left.markdown(f"**카테고리:** `{curr['category']}`")
c_right.markdown(f"<div style='text-align: right; color: #64748b;'>{st.session_state.current_index + 1} / {total}</div>", unsafe_allow_html=True)

# 1) 한국어 전체 문장 표시
korean_text = curr.get("korean_full", curr.get("korean", ""))
st.markdown(
    f"""
    <div style="background-color: #f1f5f9; padding: 16px 20px; border-radius: 10px; border-left: 5px solid #2563eb; margin: 10px 0 16px 0; font-size: 17px; font-weight: 500; color: #1e293b; line-height: 1.5;">
        🇰🇷 {korean_text}
    </div>
    """,
    unsafe_allow_html=True
)

# 2) 띄어쓰기가 명시된 말해보카 스타일 빈칸 슬롯 생성 함수
ans = curr["answer"].strip()
attempts = st.session_state.attempts

def make_spaced_slot(target_phrase, attempt_count):
    # 단어 단위로 쪼갬 (예: "follow", "up")
    words = target_phrase.split()
    word_blocks = []
    
    for word in words:
        if attempt_count <= 1:
            # 전체 빈칸
            slots = " ".join(["_"] * len(word))
        elif attempt_count == 2:
            # 첫 글자 오픈
            first = word[0]
            rest = " ".join(["_"] * (len(word) - 1)) if len(word) > 1 else ""
            slots = f"{first} {rest}".strip()
        else:
            # 두 번째 글자까지 오픈
            first_two = word[:2]
            rest = " ".join(["_"] * (len(word) - 2)) if len(word) > 2 else ""
            slots = f"{first_two[0]} {first_two[1:]} {rest}".strip()
            
        word_blocks.append(f"<span style='letter-spacing: 2px; text-decoration: underline;'>{slots}</span>")
    
    # 단어와 단어 사이(띄어쓰기)를 시각적으로 넓게 분리
    return "&nbsp;&nbsp;&nbsp;&nbsp;".join(word_blocks)

blank_html = make_spaced_slot(ans, attempts)

# 3) 영어 전체 문장 (문맥 안에서 빈칸이 자연스럽게 들어간 형태)
st.markdown(
    f"""
    <div style="background-color: #ffffff; padding: 24px; border-radius: 14px; border: 1.5px solid #cbd5e1; box-shadow: 0 2px 8px rgba(0,0,0,0.04); font-size: 20px; line-height: 1.7; color: #334155; margin-bottom: 20px;">
        🇺🇸 {curr['prefix']} 
        <span style="color: #2563eb; font-weight: 700; background-color: #eff6ff; padding: 4px 10px; border-radius: 6px; border: 1px dashed #3b82f6;">
            [ {blank_html} ]
        </span> 
        {curr['suffix']}
    </div>
    """,
    unsafe_allow_html=True
)

# --------------------------------------------------
# 7. 오답/정답 처리 로직
# --------------------------------------------------
def record_wrong():
    if not any(item['id'] == curr['id'] for item in st.session_state.wrong_notes):
        st.session_state.wrong_notes.append(curr)

def check_answer(user_input: str):
    # 공백 정규화 후 소문자 비교
    clean_input = " ".join(user_input.strip().lower().split())
    clean_target = " ".join(ans.lower().split())
    
    if clean_input == clean_target:
        st.session_state.is_correct = True
        st.session_state.feedback_msg = (
            "correct", 
            f"🎉 **정답입니다!**\n\n"
            f"✨ **완성 문장:** {curr['prefix']} **{curr['answer']}** {curr['suffix']}\n\n"
            f"📌 **실무 팁:** {curr['explanation']}"
        )
    else:
        st.session_state.attempts += 1
        record_wrong()
        if st.session_state.attempts == 1:
            st.session_state.feedback_msg = ("hint", f"❌ **다시 시도해보세요!**\n\n💡 **1차 힌트:** {curr['clue']}")
        elif st.session_state.attempts == 2:
            st.session_state.feedback_msg = ("hint", f"❌ **각 단어의 첫 글자**가 열렸습니다! 위 빈칸을 확인하세요.")
        else:
            st.session_state.feedback_msg = ("hint", f"❌ **두 번째 글자 힌트**가 열렸습니다! 조금만 더 힘내세요.")

def pass_question():
    st.session_state.attempts += 1
    record_wrong()
    if st.session_state.attempts == 1:
        st.session_state.feedback_msg = ("hint", f"💡 **1차 힌트:** {curr['clue']}")
    elif st.session_state.attempts == 2:
        st.session_state.feedback_msg = ("hint", f"💡 **첫 글자 힌트**가 열렸습니다!")
    else:
        st.session_state.feedback_msg = (
            "hint", 
            f"💡 정답은 **{curr['answer']}** 였습니다.\n\n"
            f"✨ **완성 문장:** {curr['prefix']} **{curr['answer']}** {curr['suffix']}"
        )
        st.session_state.is_correct = True

# --------------------------------------------------
# 8. 사용자 입력 인터페이스
# --------------------------------------------------
if not st.session_state.is_correct:
    with st.form("quiz_input_form", clear_on_submit=False):
        # 띄어쓰기 힌트 안내 문구 표시
        word_count_hint = f"{len(ans.split())}개 단어" if len(ans.split()) > 1 else "1개 단어"
        user_val = st.text_input(
            "영어 단어/표현 입력", 
            placeholder=f"빈칸에 들어갈 표현 입력 ({word_count_hint})", 
            label_visibility="collapsed"
        )
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

# 피드백 안내창
if st.session_state.feedback_msg:
    f_type, msg = st.session_state.feedback_msg
    if f_type == "correct":
        st.success(msg)
    else:
        st.warning(msg)

# 정답 후 다음 문제 버튼
if st.session_state.is_correct:
    if st.button("다음 문장으로 이동 ➡️", use_container_width=True):
        st.session_state.current_index += 1
        st.session_state.attempts = 0
        st.session_state.is_correct = False
        st.session_state.feedback_msg = None
        st.rerun()
