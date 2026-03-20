import streamlit as st
import google.generativeai as genai
from tavily import TavilyClient
import xlsxwriter
from io import BytesIO
from datetime import datetime
import time

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

# --- 2. Excel 문서 자동 생성 및 포맷팅 함수 ---
def create_excel_document(title, content):
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet('Research Report')
    
    # 엑셀 셀 스타일 지정 (인스파이어 보라색 포인트 및 가독성 확보)
    title_format = workbook.add_format({'bold': True, 'font_size': 16, 'font_color': '#4A148C'})
    date_format = workbook.add_format({'font_color': '#6C757D', 'italic': True})
    header_format = workbook.add_format({'bold': True, 'bg_color': '#E9ECEF', 'border': 1, 'valign': 'vcenter', 'align': 'center'})
    cell_format = workbook.add_format({'text_wrap': True, 'border': 1, 'valign': 'top'})
    text_format = workbook.add_format({'valign': 'top'}) # 텍스트 넘침 허용
    
    # 표 가독성을 위한 열 너비 세팅
    worksheet.set_column('A:A', 25) # 브랜드/IP명
    worksheet.set_column('B:B', 60) # 상세 내용
    worksheet.set_column('C:C', 40) # 성과 및 반응
    worksheet.set_column('D:D', 30) # 링크 및 기타
    worksheet.set_column('E:E', 30) 
    
    # 상단 타이틀 작성
    worksheet.write('A1', title, title_format)
    worksheet.write('A2', f"리서치 완료일: {current_date_formatted}", date_format)
    
    row = 3
    in_table = False
    
    # 마크다운 텍스트를 분석하여 엑셀 셀에 지능적으로 분배
    for line in content.split('\n'):
        line = line.strip()
        if not line:
            row += 1
            continue
            
        # 표(Table) 영역 감지
        if line.startswith('|') and line.endswith('|'):
            # 표의 구분선(|---|---|)은 엑셀에 불필요하므로 패스
            if '---' in line:
                continue
            
            cells = [cell.strip() for cell in line.split('|')[1:-1]]
            
            # 표의 헤더(첫 줄) 서식
            if not in_table:
                in_table = True
                for col_num, cell_data in enumerate(cells):
                    worksheet.write(row, col_num, cell_data, header_format)
            # 표의 본문 데이터 서식
            else:
                for col_num, cell_data in enumerate(cells):
                    worksheet.write(row, col_num, cell_data, cell_format)
            row += 1
        else:
            in_table = False
            # 표가 아닌 일반 요약/인사이트 텍스트는 A열에 작성하여 자연스럽게 넘치도록 배치
            worksheet.write(row, 0, line, text_format)
            row += 1
            
    workbook.close()
    output.seek(0)
    return output

# --- 3. 웹 UI 구성 및 디자인 ---
st.set_page_config(page_title="Marketing & IP Research Agent", layout="wide", page_icon="🔍")

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
    
    .stDownloadButton>button { background-color: #FFFFFF; color: #007233; border: 2px solid #007233; } /* 엑셀 그린 색상으로 변경 */
    .stDownloadButton>button:hover { background-color: #E8F5E9; }
    
    div[data-testid="stStatusWidget"] { background-color: #F3E5F5; border: 1px solid #4A148C; color: #4A148C; }
    
    .result-container {
        background-color: #FFFFFF; padding: 30px; border-radius: 8px; 
        border: 1px solid #DEE2E6; color: #212529; box-shadow: 0px 4px 6px rgba(0,0,0,0.05);
    }
    
    .result-container table { width: 100%; }
    .result-container th, .result-container td { word-break: keep-all; }
    
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #E9ECEF; border-radius: 6px 6px 0px 0px;
        padding: 10px 20px; color: #4A148C; font-weight: bold;
    }
    .stTabs [aria-selected="true"] { background-color: #4A148C; color: #FFFFFF !important; }
"""
st.markdown(f'<style>{inspire_style_css}</style>', unsafe_allow_html=True)

st.title("🔍 Marketing & IP Research Agent")
st.markdown("---")

# --- 4. 검색 조건 설정 (사이드바) ---
with st.sidebar:
    st.header("⚙️ 기본 환경 설정")
    st.markdown("*(이 설정은 모든 탭의 AI 분석에 최우선으로 반영됩니다)*")
    target_industry = st.selectbox("1. 자사/타겟 산업군", ["호텔/리조트", "카지노/복합리조트", "오프라인 유통/복합몰", "F&B/외식업"])
    specific_brand = st.text_input("2. 자사 브랜드명 (선택)", placeholder="예: 인스파이어, 파라다이스 등")
    
    period_options = {
        "최근 1개월": ("month", ""),
        "최근 3개월": ("year", f"{current_year}년 최근 3개월"), 
        "최근 6개월": ("year", f"{current_year}년 최근 6개월"), 
        "최근 1년": ("year", "")
    }
    selected_time = st.selectbox("3. 리서치 기간", list(period_options.keys()), index=3)
    tavily_time_range, text_time_prompt = period_options[selected_time]

# =========================================================
# --- 5. 탭(Tabs) 구성 ---
# =========================================================
tab1, tab2 = st.tabs(["📊 마케팅 트렌드 딥 리서치", "🦄 IP 콜라보 매칭 에이전트"])

# =========================================================
# [TAB 1] 마케팅 트렌드 딥 리서치 
# =========================================================
with tab1:
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

    if st.button("Deep Research 시작 (시간 소요) 🚀", key="btn1_deep"):
        if not channel_pick and not target_pick and not action_pick and not custom_query:
            st.warning("최소 하나 이상의 키워드 블록을 선택하거나 입력해주세요.")
        else:
            with st.status(f"에이전트가 {target_industry} 트렌드를 리서치 중입니다...", expanded=True) as status:
                try:
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    
                    st.write("🧠 AI가 사용자의 의도를 분석하여 최적의 검색어를 설계 중입니다...")
                    
                    intent_parts = [f"산업군: {target_industry}"]
                    if specific_brand: intent_parts.append(f"타겟브랜드: {specific_brand}")
                    if text_time_prompt: intent_parts.append(f"기간조건: {text_time_prompt}")
                    if channel_pick: intent_parts.append(f"채널: {', '.join(channel_pick)}")
                    if target_pick: intent_parts.append(f"타겟고객: {', '.join(target_pick)}")
                    if action_pick: intent_parts.append(f"캠페인방식: {', '.join(action_pick)}")
                    if custom_query: intent_parts.append(f"★필수 포함 추가키워드: {custom_query}")
                    
                    user_intent = "\n".join(intent_parts)
                    
                    query_gen_prompt = f"""
                    당신은 마케팅 리서치를 위한 '검색어 최적화(SEO) 전문가'입니다.
                    [검색어 작성 규칙]
                    1. 과도한 따옴표 금지.
                    2. 오직 [★필수 포함 추가키워드]가 있을 경우에만 해당 단어에 따옴표(" ") 적용.
                    3. 한국 기사 강제: "국내" 필수 포함.
                    4. 노이즈 차단: "-대만 -일본 -중국 -글로벌 -해외진출 -배달 -금융 -보험 -IT기업" 끝에 추가.
                    5. 검색어 1줄만 출력.
                    [사용자 선택 키워드]
                    {user_intent}
                    """
                    
                    optimized_query = model.generate_content(query_gen_prompt).text.strip()
                    st.write(f"👉 설계된 검색어: `{optimized_query}`")

                    st.write("⏳ API 호출 한도 방어를 위해 잠시 숨 고르기 중입니다 (약 5초)...")
                    time.sleep(5)

                    st.write("🔍 엄격한 필터를 적용하여 웹 데이터를 수집 중입니다...")
                    search_params = {"query": optimized_query, "search_depth": "advanced", "max_results": 12}
                    if tavily_time_range: search_params["time_range"] = tavily_time_range
                        
                    search_result = tavily_client.search(**search_params)
                    search_results_list = search_result.get('results', [])
                    
                    if not search_results_list:
                        status.update(label="검색 결과 없음", state="error", expanded=True)
                        st.error("일치하는 기사를 찾지 못했습니다. 키워드를 줄이거나 기간을 넓혀주세요.")
                        st.stop()
                        
                    context_text = "\n".join([f"- 제목: {res['title']}\n  내용: {res['content']}\n  출처 링크: {res['url']}\n" for res in search_results_list])
                    st.write(f"✅ {len(search_results_list)}개의 관련 문서를 수집했습니다.")

                    st.write("🧠 수집된 데이터를 검증하여 최상위 사례만 표로 정리 중입니다...")
                    
                    report_prompt = f"""
                    당신은 경영진에게 보고할 '데이터 기반 전략 기획 리포트'를 작성하는 깐깐한 CX/마케팅 리서처입니다.
                    [검색된 데이터]
                    {context_text}
                    [작업 규칙]
                    1. 환경 설정 완벽 준수: 타겟 산업군('{target_industry}') 사례를 최우선으로 배치하십시오.
                    2. 해외 사례 즉각 폐기: 오직 한국 내에서 열린 행사만 다루십시오.
                    3. 품질 우선주의: 구체적인 내용이 포함된 사례를 **3개~7개 사이**로 표를 구성하십시오. 
                    4. 출처 링크 포맷 강제: 표의 '출처 링크' 칸은 무조건 `[기사 보기](URL)` 형태의 마크다운 하이퍼링크로만 작성하십시오.
                    [출력 양식]
                    # 📊 마케팅 레퍼런스 리서치 리포트
                    *(분석 타겟: {target_industry} / 주요 키워드: {', '.join(channel_pick + target_pick + action_pick)} / 기간: {selected_time})*
                    ## 1. 핵심 레퍼런스 요약 (Key Highlights)
                    - 벤치마킹하기 좋은 구체적 성공 사례 2~3가지 요약. (출처 링크 포함)
                    ## 2. 주요 기업별 캠페인 상세 분석 (Case Study)
                    | 기업/브랜드명 | 주요 캠페인/이벤트 상세 내용 (진행 방식 및 특징) | 확인된 성과 및 고객 반응 | 출처 링크 |
                    |---|---|---|---|
                    | ... | ... | ... | `[기사 보기](URL)` |
                    ## 3. 실무 적용을 위한 전략적 시사점 (Actionable Insights)
                    - 우리 회사({target_industry} 산업)가 적용해볼 수 있는 구체적인 전략 방향 요약.
                    """
                    
                    report_content = model.generate_content(report_prompt).text
                    status.update(label="리서치 및 리포트 작성 완료!", state="complete", expanded=False)
                    
                    st.subheader("📈 리서치 결과 리포트")
                    st.markdown(f"<div class='result-container'>{report_content}</div>", unsafe_allow_html=True)
                    
                    # 💡 엑셀 출력 기능으로 대체
                    excel_file = create_excel_document(f"{target_industry} 트렌드 리포트", report_content)
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.download_button(
                        label="📊 Excel 리포트로 다운로드",
                        data=excel_file,
                        file_name=f"Trend_Report_{current_date_formatted}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_btn1"
                    )
                    
                except Exception as e:
                    status.update(label="오류 발생", state="error", expanded=True)
                    st.error(f"작업 중 에러가 발생했습니다: {e}")

# =========================================================
# [TAB 2] IP 콜라보 매칭 에이전트 
# =========================================================
with tab2:
    st.subheader("🦄 브랜드 맞춤형 IP/캐릭터 콜라보레이션 제안")
    st.markdown("원하는 콜라보 컨셉을 선택하시면, **인스타, X(트위터), 커뮤니티 등에서 가장 핫한 IP 후보**를 찾아 리스팅해 드립니다.")
    
    col_ip1, col_ip2 = st.columns(2)
    with col_ip1:
        ip_origin = st.selectbox("🌍 선호하는 IP 국적", ["상관없음 (국내/해외 IP 모두 포함)", "국내 IP 한정 (K-캐릭터/브랜드)", "글로벌/해외 IP 한정"], key="ip_o")
        ip_target = st.selectbox("🎯 메인 타겟 고객", ["전연령 (대중성)", "유아동/가족 단위", "1020 잘파세대", "2030 MZ세대", "3040 직장인/주부"], key="ip_t")
    with col_ip2:
        ip_goal = st.selectbox("🏆 콜라보 핵심 목적", ["오프라인 공간 방문객 유도 (팝업/전시)", "신규 멤버십 가입 유도", "SNS 바이럴 및 화제성 확보", "굿즈/F&B 상품 판매 연계"], key="ip_g")
        ip_concept = st.multiselect("🎨 원하는 콜라보 컨셉 (최대 3개)", 
                                    ["귀여운/친근한", "힙한/트렌디한", "고급스러운/럭셔리", "친환경/가치소비", "유머/B급 감성", "힐링/휴식", "예술적/아티스틱"], key="ip_c")

    if st.button("맞춤형 IP 매칭 리서치 시작 🚀", key="btn2_ip"):
        if not ip_concept:
            st.warning("원하는 콜라보 컨셉을 최소 1개 이상 선택해주세요.")
        else:
            with st.status("SNS 및 커뮤니티 트렌드를 분석하고 콜라보 후보를 찾고 있습니다...", expanded=True) as status:
                try:
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    
                    st.write("🧠 바이럴 트렌드를 긁어모으기 위한 쿼리 설계 중...")
                    
                    ip_intent_parts = [f"산업군: {target_industry}"]
                    if specific_brand: ip_intent_parts.append(f"자사브랜드: {specific_brand}")
                    if text_time_prompt: ip_intent_parts.append(f"기간조건: {text_time_prompt}")
                    ip_intent_parts.append(f"IP국적조건: {ip_origin}")
                    ip_intent_parts.append(f"타겟: {ip_target}")
                    ip_intent_parts.append(f"컨셉: {', '.join(ip_concept)}")
                    ip_intent_parts.append(f"목적: {ip_goal}")
                    
                    ip_intent = "\n".join(ip_intent_parts)
                    
                    ip_query_prompt = f"""
                    당신은 브랜드 IP 콜라보레이션 전문가입니다.
                    [사용자 조건]
                    {ip_intent}
                    [작업 규칙]
                    1. 행사 장소 한정: 콜라보 팝업이나 행사는 무조건 대한민국(한국)에서 열린 사례여야 합니다. 
                    2. SNS 및 바이럴 특화: "인스타", "트위터", "인증샷", "품절", "웨이팅" 같은 키워드를 검색어에 자연스럽게 섞으십시오.
                    3. IP 국적 반영: 사용자가 '{ip_origin}'을 선택했습니다.
                    4. 노이즈 차단: 끝에 "-대만 -일본 -중국 -해외진출 -글로벌진출" 을 반드시 붙일 것.
                    5. 검색어 1줄만 출력.
                    """
                    ip_optimized_query = model.generate_content(ip_query_prompt).text.strip()
                    st.write(f"👉 IP SNS 검색어: `{ip_optimized_query}`")

                    st.write("⏳ API 호출 한도 방어를 위해 잠시 숨 고르기 중입니다 (약 5초)...")
                    time.sleep(5)
                    
                    st.write("🔍 최신 SNS 게시물 및 기사 동향을 수집 중입니다...")
                    search_params_ip = {"query": ip_optimized_query, "search_depth": "advanced", "max_results": 15} 
                    if tavily_time_range: search_params_ip["time_range"] = tavily_time_range
                        
                    ip_search_result = tavily_client.search(**search_params_ip)
                    ip_results_list = ip_search_result.get('results', [])
                    
                    if not ip_results_list:
                        status.update(label="검색 결과 없음", state="error", expanded=True)
                        st.error("관련된 IP 트렌드 기사를 찾지 못했습니다. 컨셉을 변경해 보세요.")
                        st.stop()
                        
                    ip_context = "\n".join([f"- 제목: {res['title']}\n  내용: {res['content']}\n  링크: {res['url']}\n" for res in ip_results_list])
                    st.write(f"✅ {len(ip_results_list)}개의 IP 트렌드 문서를 분석합니다.")
                    
                    st.write("🎯 브랜드 핏에 맞는 IP 후보들을 긁어모아 리스트를 작성 중입니다...")
                    
                    ip_report_prompt = f"""
                    당신은 {target_industry} 산업의 브랜드 기획자입니다. 우리 브랜드({specific_brand if specific_brand else '자사'})를 위한 최고의 IP 콜라보레이션 후보를 제안해야 합니다.
                    [검색된 최신 데이터]
                    {ip_context}
                    [사용자 요구 조건]
                    {ip_intent}
                    [작업 규칙 - 절대 엄수]
                    1. 해외 행사 즉각 폐기: 그 IP가 진행한 행사가 대한민국(한국) 영토 밖에서 열린 것이라면 무조건 표에서 폐기하십시오.
                    2. 수량 확보: 검색된 문서의 본문을 살펴서 가능한 모든 IP 후보를 쥐어짜 내어 **5개~10개 내외**로 리스팅하십시오.
                    3. 맞춤형 아이디어 기획: 각 IP를 우리의 특정 타겟 산업군({target_industry}) 오프라인 공간이나 서비스에 어떻게 적용할 것인지 구체적인 아이디어를 제안하십시오.
                    4. 출처 링크: 데이터에서 참고한 경우 `[기사 보기](URL)` 형태로 짧게 링크를 첨부하십시오.
                    [출력 양식]
                    # 🦄 맞춤형 IP 콜라보레이션 매칭 리포트
                    *(타겟 산업군: {target_industry} / 요구 IP 국적: {ip_origin})*
                    ## 1. 최신 IP 트렌드 요약
                    - 현재 선택된 타겟층({ip_target})이 SNS에서 열광하는 콜라보 트렌드 특징을 2~3줄로 요약.
                    ## 2. 추천 IP 후보 리스트 (5~10개)
                    | 추천 IP (캐릭터/브랜드명) | {target_industry} 산업 추천 이유 | 💡 콜라보 아이디어 (공간/이벤트 적용 방안) | 참고 링크 |
                    |---|---|---|---|
                    | ... | ... | ... | `[기사 보기](URL)` |
                    ## 3. 기획자 코멘트 (Next Step)
                    - 위 후보 중 가장 강력하게 추천하는 1가지와 실무 진행 시 고려해야 할 점 1~2줄 요약.
                    """
                    
                    ip_report_content = model.generate_content(ip_report_prompt).text
                    status.update(label="IP 매칭 리포트 완성!", state="complete", expanded=False)
                    
                    st.subheader("🎯 IP 콜라보레이션 제안서")
                    st.markdown(f"<div class='result-container'>{ip_report_content}</div>", unsafe_allow_html=True)
                    
                    # 💡 엑셀 출력 기능으로 대체
                    excel_file_ip = create_excel_document("IP 콜라보 제안 리포트", ip_report_content)
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.download_button(
                        label="📊 Excel 제안서로 다운로드", 
                        data=excel_file_ip, 
                        file_name=f"IP_Collab_Proposal_{current_date_formatted}.xlsx", 
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                        key="dl_btn2"
                    )
                    
                except Exception as e:
                    status.update(label="오류 발생", state="error", expanded=True)
                    st.error(f"에러: {e}")
