import streamlit as st
import google.generativeai as genai
from tavily import TavilyClient
from docx import Document
from io import BytesIO
from datetime import datetime

# --- 1. API 키 세팅 ---
try:
    TAVILY_API_KEY = st.secrets["TAVILY_API_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except KeyError:
    st.error("API 키가 secrets.toml에 설정되지 않았습니다.")
    st.stop()

tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
genai.configure(api_key=GEMINI_API_KEY)

current_year = datetime.now().year
current_date_formatted = datetime.now().strftime('%Y-%m-%d')

# --- 2. Word 문서 생성 함수 ---
def create_word_document(title, content):
    doc = Document()
    doc.add_heading(title, 0)
    doc.add_paragraph(f"리서치 수행일: {current_date_formatted}")
    doc.add_paragraph("\n--- 데이터 리서치 결과 ---\n")
    doc.add_paragraph(content)
    file_stream = BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)
    return file_stream

# --- 3. 웹 UI 구성 및 디자인 ---
st.set_page_config(page_title="Marketing Trend Research Agent", layout="wide", page_icon="🔍")

inspire_style_css = """
    header, [data-testid="stDecoration"] { display: none; }
    .stApp { background-color: #F8F9FA; }
    [data-testid="stSidebar"] { background-color: #E9ECEF; border-right: 1px solid #DEE2E6; }
    
    h1, h2, h3, h4, [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] label {
        color: #4A148C !important; font-weight: 800;
    }
    
    .stButton>button {
        background-color: #4A148C; color: #FFFFFF; border: 2px solid #4A148C;
        border-radius: 6px; font-weight: bold; width: 100%; transition: 0.3s;
    }
    .stButton>button:hover {
        background-color: #E9ECEF; border-color: #4A148C; color: #4A148C;
    }
    
    .stDownloadButton>button { background-color: #FFFFFF; color: #4A148C; border: 2px solid #4A148C; }
    .stDownloadButton>button:hover { background-color: #F3E5F5; }
    
    div[data-testid="stStatusWidget"] { background-color: #F3E5F5; border: 1px solid #4A148C; color: #4A148C; }
    
    .result-container {
        background-color: #FFFFFF; padding: 30px; border-radius: 8px; 
        border: 1px solid #DEE2E6; color: #212529; box-shadow: 0px 4px 6px rgba(0,0,0,0.05);
    }
    
    .result-container table { width: 100%; }
    .result-container th, .result-container td { word-break: keep-all; }
"""
st.markdown(f'<style>{inspire_style_css}</style>', unsafe_allow_html=True)

st.title("🔍 Marketing Trend Research Agent")
st.markdown("---")

# --- 4. 검색 조건 설정 (사이드바) ---
with st.sidebar:
    st.header("⚙️ 리서치 기본 설정")
    target_industry = st.selectbox("1. 타겟 산업군 (필수)", ["호텔/리조트", "카지노/복합리조트", "오프라인 유통/복합몰", "F&B/외식업"])
    specific_brand = st.text_input("2. 특정 타겟 브랜드 (선택)", placeholder="예: 파라다이스, 더현대 등")
    
    period_options = {
        "최근 1개월": ("month", ""),
        "최근 3개월": ("year", f"{current_year}년 최근 3개월"), 
        "최근 6개월": ("year", f"{current_year}년 최근 6개월"), 
        "최근 1년": ("year", ""),
        "최근 3년": ("any", f"{current_year - 3}년 이후부터 {current_year}년까지")
    }
    selected_time = st.selectbox("3. 리서치 기간", list(period_options.keys()), index=3)
    tavily_time_range, text_time_prompt = period_options[selected_time]

# --- 5. 레고 블록형 리서치 키워드 조합 (메인 화면) ---
st.subheader("💡 리서치 키워드 조합 (모듈형)")
st.markdown("원하는 타겟, 채널, 캠페인 방식을 자유롭게 조합하세요. AI가 최적의 검색어로 번역하여 리서치합니다.")

col1, col2, col3 = st.columns(3)
with col1:
    channel_pick = st.multiselect("📍 채널 (Channel)", ["오프라인 전용", "온라인/앱(App)", "온·오프라인 연계(O2O)"])
with col2:
    target_pick = st.multiselect("🎯 타겟 고객 (Target)", ["신규 가입자", "VIP/우수고객", "휴면 고객", "2030 MZ세대", "가족 단위", "외국인 관광객"])
with col3:
    action_pick = st.multiselect("🚀 캠페인 방식 (Action)", ["멤버십 론칭/개편", "유료 멤버십", "팝업/공간 마케팅", "할인/바우처 프로모션", "프라이빗 초청 행사", "브랜드/캐릭터 콜라보"])

custom_query = st.text_input("✍️ 추가 자유 키워드 (선택)", placeholder="예: 두바이 초콜릿, 크리스마스 팝업, 팝업스토어 웨이팅 등 특별히 포함하고 싶은 단어")

# 리서치 실행 버튼
if st.button("Deep Research 시작 (시간 소요) 🚀"):
    if not channel_pick and not target_pick and not action_pick and not custom_query:
        st.warning("최소 하나 이상의 키워드 블록을 선택하거나 입력해주세요.")
    else:
        with st.status(f"에이전트가 {target_industry} 트렌드를 딥 리서치 중입니다. (약 15~30초 소요)...", expanded=True) as status:
            try:
                model = genai.GenerativeModel('gemini-2.5-flash')
                
                # =========================================================
                # [단계 1] AI 중간 해석 (Query Expansion) - 따옴표 남발 방지
                # =========================================================
                st.write("🧠 AI가 사용자의 의도를 분석하여 최적의 검색어를 설계 중입니다...")
                
                intent_parts = [f"산업군: {target_industry}"]
                if specific_brand: intent_parts.append(f"타겟브랜드: {specific_brand}")
                if channel_pick: intent_parts.append(f"채널: {', '.join(channel_pick)}")
                if target_pick: intent_parts.append(f"타겟고객: {', '.join(target_pick)}")
                if action_pick: intent_parts.append(f"캠페인방식: {', '.join(action_pick)}")
                if custom_query: intent_parts.append(f"★필수 포함 추가키워드: {custom_query}")
                
                user_intent = "\n".join(intent_parts)
                
                query_gen_prompt = f"""
                당신은 마케팅 리서치를 위한 '검색어 최적화(SEO) 전문가'입니다.
                아래 [사용자 선택 키워드]를 참고하여, 검색 엔진에서 가장 유의미한 '대한민국 마케팅 성공 사례 기사'를 찾을 수 있는 **검색어 문자열 1줄만** 출력하십시오.
                
                [사용자 선택 키워드]
                {user_intent}
                
                [검색어 작성 규칙 - 절대 엄수]
                1. 과도한 따옴표 금지 (가장 중요): 모든 단어에 따옴표("")를 씌우지 마십시오. 검색 결과가 0개가 됩니다. 주요 키워드를 자연스러운 띄어쓰기로 나열하십시오. (예: 국내 오프라인 유통 복합몰 팝업스토어 프로모션 사례)
                2. 강력한 필수 포함: 오직 [★필수 포함 추가키워드]가 있을 경우에만, 해당 단어 하나에만 따옴표(" ")를 씌워 검색어에 포함하십시오.
                3. 한국 기사 강제: "국내" 라는 단어를 반드시 포함할 것.
                4. 해외 및 노이즈 차단: 문장 끝에 반드시 "-대만 -일본 -중국 -글로벌 -해외 -배달 -금융 -보험 -IT기업" 을 붙일 것.
                5. 오직 완성된 검색어 1줄만 출력할 것.
                """
                
                optimized_query = model.generate_content(query_gen_prompt).text.strip()
                st.write(f"👉 설계된 검색어: `{optimized_query}`")

                # =========================================================
                # [단계 2] Tavily 데이터 수집 및 예외 처리
                # =========================================================
                st.write("🔍 엄격한 필터를 적용하여 웹 데이터를 광범위하게 수집 중입니다...")
                
                search_params = {
                    "query": optimized_query,
                    "search_depth": "advanced",
                    "max_results": 25
                }
                if tavily_time_range:
                    search_params["time_range"] = tavily_time_range
                    
                search_result = tavily_client.search(**search_params)
                search_results_list = search_result.get('results', [])
                
                # 💡 결과가 0개일 경우를 대비한 안전장치 추가
                if not search_results_list:
                    status.update(label="검색 결과 없음", state="error", expanded=True)
                    st.error("앗! 선택하신 키워드 조합이 너무 구체적이어서 일치하는 기사를 하나도 찾지 못했습니다. 🎯 키워드 개수를 조금 줄이거나 범위를 넓혀서 다시 시도해 주세요.")
                    st.stop() # 여기서 멈춤 (리포트 작성으로 넘어가지 않음)
                    
                context_text = "\n".join([f"- 제목: {res['title']}\n  내용: {res['content']}\n  출처 링크: {res['url']}\n" for res in search_results_list])
                st.write(f"✅ {len(search_results_list)}개의 관련 문서를 수집했습니다.")

                # =========================================================
                # [단계 3] AI 최종 리포트 작성
                # =========================================================
                st.write("🧠 수집된 데이터를 깐깐하게 검증하여 최상위 사례만 표로 정리 중입니다...")
                
                report_prompt = f"""
                당신은 경영진에게 보고할 '데이터 기반 전략 기획 리포트'를 작성하는 최고 수준의 깐깐한 CX/마케팅 리서처입니다.
                아래 수집된 방대한 데이터를 바탕으로 리포트를 작성하되, **반드시 아래 규칙을 엄수**하십시오.

                [검색된 데이터]
                {context_text}

                [작업 규칙 - 절대 엄수]
                1. 해외 사례 즉각 폐기: 대한민국 영토 밖에서 벌어진 일이나 글로벌 사례는 무조건 제외하십시오.
                2. 품질 우선주의 (Quality over Quantity): 사용자 의도에 완벽히 부합하고 내용이 구체적인 **고퀄리티 사례만 엄선하여 5개~15개 사이**로 표를 구성하십시오. 
                3. 출처 링크 포맷 강제: 표의 '출처 링크' 칸에 긴 URL을 쓰지 마십시오. **무조건 `[기사 보기](URL)` 형태의 마크다운 하이퍼링크로만 작성**하십시오.
                4. 이벤트 디테일 묘사: **어떤 기업이, 누구를 대상으로, 무엇을 어떻게 했는지** 상세하게 묘사하십시오.
                5. 정량적 성과 포함: 사례 설명 시 수치적 성과가 있다면 함께 적고, 없다면 억지로 만들지 마십시오.

                [출력 양식]
                # 📊 마케팅 레퍼런스 딥 리서치 리포트

                *(분석 타겟: {target_industry} / 주요 키워드: {', '.join(channel_pick + target_pick + action_pick)} {f'/ 추가 키워드: {custom_query}' if custom_query else ''})*

                ## 1. 핵심 레퍼런스 요약 (Key Highlights)
                - 수집된 데이터 중 가장 벤치마킹하기 좋은 구체적 성공 사례 2~3가지를 요약. (출처 링크 포함)

                ## 2. 주요 기업별 캠페인 상세 분석 (Case Study)
                | 기업/브랜드명 | 주요 캠페인/이벤트 상세 내용 (진행 방식 및 특징) | 확인된 성과 및 고객 반응 | 출처 링크 |
                |---|---|---|---|
                | ... | ... | ... | `[기사 보기](URL)` |

                ## 3. 실무 적용을 위한 전략적 시사점 (Actionable Insights)
                - 위 사례들을 종합하여, 우리 회사가 실제 기획 시 적용해볼 수 있는 구체적인 전략 방향 요약.
                """
                
                report_content = model.generate_content(report_prompt).text
                status.update(label="딥 리서치 및 리포트 작성 완료!", state="complete", expanded=False)
                
                # 결과 출력
                st.subheader("📈 딥 리서치 결과 리포트")
                st.markdown(f"<div class='result-container'>{report_content}</div>", unsafe_allow_html=True)
                
                # 다운로드 버튼
                docx_file = create_word_document(f"트렌드 리포트", report_content)
                st.markdown("<br>", unsafe_allow_html=True)
                st.download_button(
                    label="📥 Word 문서로 다운로드",
                    data=docx_file,
                    file_name=f"Deep_Research_Report_{current_date_formatted}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
                
            except Exception as e:
                status.update(label="오류 발생", state="error", expanded=True)
                st.error(f"작업 중 에러가 발생했습니다: {e}")