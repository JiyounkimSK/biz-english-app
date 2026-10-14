import json
import os
import streamlit as st
from google import genai
from google.genai import types

# --------------------------------------------------
# 페이지 기본 설정
# --------------------------------------------------
st.set_page_config(
    page_title="Biz English Daily 30",
    page_icon="💼",
    layout="centered"
)

# --------------------------------------------------
# 세션 상태(State) 초기화
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
# Gemini API 호출 및 30개 단어 생성 로직
# --------------------------------------------------
def generate_daily_words(api_key: str, count: int = 30):
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
당신은 비즈니스 영어 교육 전문가입니다.
회사 업무(기획, 전략, 리소스 배분, 이메일 커뮤니케이션, 미팅 조율, 리스크 관리 등)에서 바로 사용할 수 있는 실무 비즈니스 영어 표현 {count}개를 생성해주세요.

반드시 아래 JSON 스키마를 준수하는 유효한 JSON 배열만 응답하세요. 다른 설명이나 마크다운 서식(백틱)은 포함하지 마세요.

JSON Array Item Schema:
{{
  "id": number,
  "category": "Email" | "Meeting" | "Planning" | "Operations",
  "korean": "핵심 표현이 강조된 자연스러운 한국어 업무 상황 문장 (강조 단어는 [ ] 표시)",
  "prefix": "빈칸 앞 영어 문장",
  "answer": "빈칸에 들어갈 영어 단어 또는 숙어(소문자)",
  "suffix": "빈칸 뒤 영어 문장",
  "clue": "1차 힌트로 제공할 품사 및 뉘앙스 설명",
  "explanation": "해당 단어의 실무 뉘앙스 및 대체 표현 팁"
}}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.7,
        ),
    )
    
    data = json.loads(response.text)
    return data

# --------------------------------------------------
# 사이드바: API 설정 및 오답노트
# --------------------------------------------------
with st.sidebar:
    st.title("⚙️ 설정 & 데이터")
    api_key = st.text_input("Gemini API Key", type="password", help="Google AI Studio에서 발급받은 API 키를 입력하세요.")
    word_count = st.slider("학습 단어 수", min_value=5, max_value=30, value=30, step=5)
    
    if st.button("🚀 오늘의 단어 세트 생성", use_container_width=True):
        if not api_key:
            st.error("API 키를 먼저 입력해주세요.")
        else:
            with st.spinner("비즈니스 실무 단어를 지능형으로 선별 중..."):
                try:
                    words = generate_daily_words(api_key, count=word_count)
                    st.session_state.word_list = words
                    st.session_state.current_index = 0
                    st.session_state.attempts = 0
                    st.session_state.is_correct = False
                    st.session_state.feedback_msg = None
                    st.success(f"{len(words)}개 단어 준비 완료!")
                    st.rerun()
                except Exception as e:
                    st.error(f"생성 실패: {e}")

    st.divider()
    st.subheader(f"📝 오답 노트 ({len(st.session_state.wrong_notes)}개)")
    if st.session_state.wrong_notes:
        for idx, item in enumerate(st.session_state.wrong_notes):
            with st.expander(f"{idx+1}. {item['answer']} ({item['category']})"):
                st.write(f"**상황:** {item['korean']}")
                st.write(f"**문장:** {item['prefix']} **{item['answer']}** {item['suffix']}")
                st.caption(item['explanation'])
        
        if st.button("오답 노트 초기화", use_container_width=True):
            st.session_state.wrong_notes = []
            st.rerun()

# --------------------------------------------------
# 메인 퀴즈 인터페이스
# --------------------------------------------------
st.title("💼 Biz English Daily Study")

if not st.session_state.word_list:
    st.info("왼쪽 사이드바에 API 키를 입력하고 **[오늘의 단어 세트 생성]** 버튼을 눌러주세요.")
    st.stop()

# 모든 단어 학습 완료 시
if st.session_state.current_index >= len(st.session_state.word_list):
    st.balloons()
    st.success("🎉 오늘 목표한 단어 학습을 모두 마쳤습니다!")
    st.metric("총 학습 단어", f"{len(st.session_state.word_list)}개")
    st.metric("오답 등록 단어", f"{len(st.session_state.wrong_notes)}개")
    
    if st.button("다시 처음부터 풀기", use_container_width=True):
        st.session_state.current_index = 0
        st.session_state.attempts = 0
        st.session_state.is_correct = False
        st.session_state.feedback_msg = None
        st.rerun()
    st.stop()

# 현재 단어 정보
curr = st.session_state.word_list[st.session_state.current_index]
total = len(st.session_state.word_list)
progress_ratio = (st.session_state.current_index) / total

st.progress(progress_ratio)
col_cat, col_num = st.columns([1, 1])
with col_cat:
    st.markdown(f"**분야:** `{curr['category']}`")
with col_num:
    st.markdown(f"<div style='text-align: right; color: gray;'>진행도: {st.session_state.current_index + 1} / {total}</div>", unsafe_allow_html=True)

# 한국어 문맥
st.info(f"💡 {curr['korean']}")

# 글자 수 힌트 슬롯 구성 (말해보카 스타일)
ans = curr["answer"].strip()
attempts = st.session_state.attempts

def make_slot(target_word, attempt_count):
    tokens = target_word.split(" ")
    result_tokens = []
    
    for token in tokens:
        if attempt_count == 0 or attempt_count == 1:
            result_tokens.append(" ".join(["_"] * len(token)))
        elif attempt_count == 2:
            # 첫 글자 노출
            first = token[0]
            rest = " ".join(["_"] * (len(token) - 1)) if len(token) > 1 else ""
            result_tokens.append(f"{first} {rest}".strip())
        else:
            # 두 번째 글자까지 노출
            first_two = token[:2]
            rest = " ".join(["_"] * (len(token) - 2)) if len(token) > 2 else ""
            result_tokens.append(f"{first_two[0]} {first_two[1:]} {rest}".strip())
            
    return "   ".join(result_tokens)

slot_display = make_slot(ans, attempts)

# 영어 문장 표시
st.markdown(
    f"""
    <div style="background-color: #f8fafc; padding: 20px; border-radius: 10px; border: 1px solid #e2e8f0; font-size: 19px; line-height: 1.6; margin: 15px 0;">
        {curr['prefix']} <strong style="color: #2563eb; letter-spacing: 2px;">[ {slot_display} ]</strong> {curr['suffix']}
    </div>
    """,
    unsafe_allow_html=True
)

# --------------------------------------------------
# 정답 판별 및 버튼 동작
# --------------------------------------------------
def record_wrong():
    # 중복 저장 방지
    if not any(item['id'] == curr['id'] for item in st.session_state.wrong_notes):
        st.session_state.wrong_notes.append(curr)

def check_answer(user_input: str):
    clean_input = user_input.strip().lower()
    clean_target = ans.lower()
    
    if clean_input == clean_target:
        st.session_state.is_correct = True
        st.session_state.feedback_msg = ("correct", f"🎉 **정답입니다!**\n\n📌 **실무 팁:** {curr['explanation']}")
    else:
        st.session_state.attempts += 1
        record_wrong()
        
        if st.session_state.attempts == 1:
            st.session_state.feedback_msg = ("hint", f"❌ **틀렸습니다!** 다시 생각해보세요.\n\n💡 **1차 힌트:** {curr['clue']}")
        elif st.session_state.attempts == 2:
            st.session_state.feedback_msg = ("hint", f"❌ **첫 글자 힌트**가 열렸습니다! 글자 슬롯을 확인하세요.")
        else:
            st.session_state.feedback_msg = ("hint", f"❌ **두 번째 글자 힌트**가 열렸습니다! 앞 두 글자를 참고하세요.")

def pass_question():
    st.session_state.attempts += 1
    record_wrong()
    if st.session_state.attempts == 1:
        st.session_state.feedback_msg = ("hint", f"💡 **1차 힌트:** {curr['clue']}")
    elif st.session_state.attempts == 2:
        st.session_state.feedback_msg = ("hint", f"💡 **첫 글자 힌트**가 열렸습니다!")
    else:
        st.session_state.feedback_msg = ("hint", f"💡 **두 번째 글자 힌트**가 열렸습니다! 정답은 **{curr['answer']}** 였습니다.")
        st.session_state.is_correct = True

# 입력 폼
if not st.session_state.is_correct:
    with st.form("quiz_form", clear_on_submit=False):
        user_val = st.text_input("영어 단어/구동사 입력", placeholder="소문자로 입력 후 Enter", label_visibility="collapsed")
        c1, c2 = st.columns([3, 1])
        with c1:
            submitted = st.form_submit_button("확인", use_container_width=True)
        with c2:
            passed = st.form_submit_button("모름 (힌트)", use_container_width=True)
            
        if submitted and user_val:
            check_answer(user_val)
            st.rerun()
        elif passed:
            pass_question()
            st.rerun()

# 피드백 메시지 출력
if st.session_state.feedback_msg:
    f_type, msg = st.session_state.feedback_msg
    if f_type == "correct":
        st.success(msg)
    else:
        st.warning(msg)

# 정답 맞춘 후 '다음 문제' 버튼
if st.session_state.is_correct:
    if st.button("다음 문제로 이동 ➡️", use_container_width=True):
        st.session_state.current_index += 1
        st.session_state.attempts = 0
        st.session_state.is_correct = False
        st.session_state.feedback_msg = None
        st.rerun()
