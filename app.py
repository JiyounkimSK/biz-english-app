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
if "user_id" not in st.session_state:
    st.session_state.user_id = ""
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

# 환경 변수 로드
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")

# --------------------------------------------------
# 3. Supabase REST API 연동 함수 (파이썬 기본 내장 모듈 사용)
# --------------------------------------------------
def save_log_to_db(user_id: str, item: dict, attempts: int, is_correct: bool):
    """문항 풀이 결과를 Supabase에 비동기/실시간 저장"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return
    
    endpoint = f"{SUPABASE_URL}/rest/v1/user_logs"
    payload = {
        "user_id": user_id,
        "question_id": item.get("id", 0),
        "category": item.get("category", ""),
        "korean_full": item.get("korean_full", item.get("korean", "")),
        "prefix": item.get("prefix", ""),
        "answer": item.get("answer", ""),
        "suffix": item.get("suffix", ""),
        "attempts": attempts,
        "is_correct": is_correct,
        "explanation": item.get("explanation", "")
    }
    
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5):
            pass
    except Exception:
        pass  # 학습 흐름이 끊기지 않도록 DB 기록 실패는 백그라운드 처리

def get_user_weak_words(user_id: str, limit: int = 10):
    """해당 사용자가 최근 자주 틀린 취약 단어 목록 추출"""
    if not SUPABASE_URL or not SUPABASE_KEY or not user_id:
        return []
    
    endpoint = f"{SUPABASE_URL}/rest/v1/user_logs?user_id=eq.{user_id}&is_correct=eq.false&select=answer&limit=50"
    req = urllib.request.Request(
        endpoint,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            logs = json.loads(res.read().decode("utf-8"))
            words = [row["answer"] for row in logs if "answer" in row]
            # 빈도수 상위 단어 정렬
            freq = {}
            for w in words:
                freq[w] = freq.get(w, 0) + 1
            sorted_words = sorted(freq.keys(), key=lambda x: freq[x], reverse=True)
            return sorted_words[:limit]
    except Exception:
        return []

# --------------------------------------------------
# 4. Gemini 개인화 문장 생성 함수
# --------------------------------------------------
def generate_personalized_words(api_key: str, count: int, weak_words: list):
    models_to_try = [
        "gemini-3.8-flash",
        "gemini-3.8-pro",
        "gemini-3.5-flash",
        "gemini-3.0-flash"
    ]
    
    weak_context = ""
    if weak_words:
        weak_context = f"""
[개인화 복습 반영 요청]
사용자가 이전에 자주 틀린 취약 표현 목록입니다: {', '.join(weak_words)}
전체 {count}개 중 30% 내외는 위 취약 표현들을 새로운 실무 문맥 예문으로 재구성하여 출제해주세요.
나머지는 기획/전략/협업 실무에 유용한 새로운 표현으로 채워주세요.
"""

    prompt = f"""
당신은 비즈니스 영어 교육 전문가입니다.
회사 실무(기획, 전략, 리소스 배분, 이메일 커뮤니케이션, 미팅 조율, 리스크 관리 등)에서 바로 사용할 수 있는 완결된 전체 문장 {count}개를 생성해주세요.
{weak_context}

반드시 다른 부가 설명 없이 순수 JSON 배열([ ... ])만 반환하세요:
[
  {{
    "id": 1,
    "category": "Email",
    "korean_full": "앞서 논의된 대로, 우리는 다음 단계로 [진행할] 예정입니다.",
    "prefix": "As discussed earlier, we will",
    "answer": "proceed",
    "suffix": "with the next phase.",
    "clue": "동사 / 공식적인 석상에서 '앞으로 나아가다'",
    "explanation": "'start'나 'go ahead' 대신 공식 이메일에서 주로 쓰이는 격식 표현입니다."
  }}
]
"""
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
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
                    return json.loads(raw_text.strip())
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

    raise RuntimeError(f"문장 생성 실패: {last_err}")

# --------------------------------------------------
# 5. 메인 로그인 및 초기 설정 화면
# --------------------------------------------------
st.title("💼 Biz English Daily Study")

if not st.session_state.word_list:
    st.markdown("### 👤 사용자 설정 및 학습 시작")
    
    # 1) 개인 아이디 입력
    user_input_id = st.text_input(
        "사용자 ID 입력 (개인별 오답 및 이력 저장용)", 
        value=st.session_state.user_id,
        placeholder="예: jiyoun"
    )
    if user_input_id:
        st.session_state.user_id = user_input_id.strip()

    # 2) API 키 자동 확인
    target_api_key = GEMINI_API_KEY
    if not target_api_key:
        target_api_key = st.text_input("Gemini API Key를 입력하세요", type="password")
    else:
        st.caption("🔒 Secrets의 API Key가 안전하게 연동되었습니다.")

    col1, col2 = st.columns([2, 1])
    with col1:
        word_count = st.slider("학습할 문장 수", min_value=5, max_value=30, value=30, step=5)
    with col2:
        st.write("")
        st.write("")
        start_btn = st.button("개인화 학습 시작 🚀", use_container_width=True)

    if start_btn:
        if not st.session_state.user_id:
            st.error("사용자 ID를 입력해주세요.")
        elif not target_api_key:
            st.error("Gemini API Key를 입력해주세요.")
        else:
            with st.spinner(f"'{st.session_state.user_id}'님의 누적 취약 단어를 분석하여 맞춤형 세트를 생성 중입니다..."):
                try:
                    # 취약 단어 이력 조회 후 Gemini 프롬프트에 자동 반영
                    weak_words = get_user_weak_words(st.session_state.user_id)
                    words = generate_personalized_words(target_api_key, count=word_count, weak_words=weak_words)
                    
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
# 6. 학습 완료 화면
# --------------------------------------------------
if st.session_state.current_index >= len(st.session_state.word_list):
    st.balloons()
    st.success(f"🎉 '{st.session_state.user_id}'님, 오늘 학습을 모두 완료했습니다! 이력이 DB에 저장되었습니다.")
    
    col_a, col_b = st.columns(2)
    col_a.metric("총 학습 문장", f"{len(st.session_state.word_list)}개")
    col_b.metric("오답 문장", f"{len(st.session_state.wrong_notes)}개")
    
    if st.session_state.wrong_notes:
        st.subheader("📝 오늘 틀린 문장 복습")
        for item in st.session_state.wrong_notes:
            with st.expander(f"📌 {item['answer']} ({item['category']})"):
                st.write(f"**한국어:** {item.get('korean_full', item.get('korean', ''))}")
                st.write(f"**완성 문장:** {item['prefix']} **{item['answer']}** {item['suffix']}")
                st.caption(item['explanation'])

    if st.button("다음 세트 학습하기", use_container_width=True):
        st.session_state.word_list = []
        st.session_state.current_index = 0
        st.session_state.attempts = 0
        st.session_state.is_correct = False
        st.session_state.feedback_msg = None
        st.rerun()
    st.stop()

# --------------------------------------------------
# 7. 단어 퀴즈 화면 (전체 문맥 + 띄어쓰기 슬롯)
# --------------------------------------------------
curr = st.session_state.word_list[st.session_state.current_index]
total = len(st.session_state.word_list)

st.progress((st.session_state.current_index) / total)
c_left, c_right = st.columns([1, 1])
c_left.markdown(f"**사용자:** `{st.session_state.user_id}` | `{curr['category']}`")
c_right.markdown(f"<div style='text-align: right; color: #64748b;'>{st.session_state.current_index + 1} / {total}</div>", unsafe_allow_html=True)

# 한국어 전체 문장
korean_text = curr.get("korean_full", curr.get("korean", ""))
st.markdown(
    f"""
    <div style="background-color: #f1f5f9; padding: 16px 20px; border-radius: 10px; border-left: 5px solid #2563eb; margin: 10px 0 16px 0; font-size: 17px; font-weight: 500; color: #1e293b; line-height: 1.5;">
        🇰🇷 {korean_text}
    </div>
    """,
    unsafe_allow_html=True
)

# 띄어쓰기가 반영된 슬롯 함수
ans = curr["answer"].strip()
attempts = st.session_state.attempts

def make_spaced_slot(target_phrase, attempt_count):
    words = target_phrase.split()
    word_blocks = []
    for word in words:
        if attempt_count <= 1:
            slots = " ".join(["_"] * len(word))
        elif attempt_count == 2:
            first = word[0]
            rest = " ".join(["_"] * (len(word) - 1)) if len(word) > 1 else ""
            slots = f"{first} {rest}".strip()
        else:
            first_two = word[:2]
            rest = " ".join(["_"] * (len(word) - 2)) if len(word) > 2 else ""
            slots = f"{first_two[0]} {first_two[1:]} {rest}".strip()
        word_blocks.append(f"<span style='letter-spacing: 2px; text-decoration: underline;'>{slots}</span>")
    return "&nbsp;&nbsp;&nbsp;&nbsp;".join(word_blocks)

blank_html = make_spaced_slot(ans, attempts)

# 영어 문장 카드
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

# 채점 및 DB 저장 연동
def record_wrong():
    if not any(item['id'] == curr['id'] for item in st.session_state.wrong_notes):
        st.session_state.wrong_notes.append(curr)

def check_answer(user_input: str):
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
        # 성공 로그 DB 저장
        save_log_to_db(st.session_state.user_id, curr, st.session_state.attempts + 1, True)
    else:
        st.session_state.attempts += 1
        record_wrong()
        # 실패 로그 DB 저장
        save_log_to_db(st.session_state.user_id, curr, st.session_state.attempts, False)
        
        if st.session_state.attempts == 1:
            st.session_state.feedback_msg = ("hint", f"❌ **다시 시도해보세요!**\n\n💡 **1차 힌트:** {curr['clue']}")
        elif st.session_state.attempts == 2:
            st.session_state.feedback_msg = ("hint", f"❌ **각 단어의 첫 글자**가 열렸습니다! 위 빈칸을 확인하세요.")
        else:
            st.session_state.feedback_msg = ("hint", f"❌ **두 번째 글자 힌트**가 열렸습니다!")

def pass_question():
    st.session_state.attempts += 1
    record_wrong()
    save_log_to_db(st.session_state.user_id, curr, st.session_state.attempts, False)
    
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

# 입력 양식
if not st.session_state.is_correct:
    with st.form("quiz_input_form", clear_on_submit=False):
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

# 힌트 및 정답 출력
if st.session_state.feedback_msg:
    f_type, msg = st.session_state.feedback_msg
    if f_type == "correct":
        st.success(msg)
    else:
        st.warning(msg)

# 다음 문장 이동 버튼
if st.session_state.is_correct:
    if st.button("다음 문장으로 이동 ➡️", use_container_width=True):
        st.session_state.current_index += 1
        st.session_state.attempts = 0
        st.session_state.is_correct = False
        st.session_state.feedback_msg = None
        st.rerun()
