# 주식 분석 대시보드 앱 개발 Task List

- [ ] **프로젝트 설정 및 의존성 관리**
    - [ ] `requirements.txt` 생성 및 라이브러리 설치 (`streamlit`, `pykrx`, `pandas`, `plotly`)
    - [ ] 프로젝트 디렉토리 구조 생성 (`pages`, `utils`, `data`)

- [ ] **백엔드 로직 모듈화 (Utils)**
    - [ ] `utils/data_fetcher.py`: `pykrx` 기반 데이터 수집 함수 (지수, 수급, 종목 리스트)
    - [ ] `utils/analysis.py`: `swing_screener.py` 로직을 함수형으로 변환 (분석 결과 DataFrame 반환)

- [ ] **프론트엔드 (Streamlit Pages) - 모바일 최적화**
    - [ ] `app.py`: 메인 페이지 및 사이드바 (반응형 레이아웃)
    - [ ] `pages/1_Daily_Top_Down.py`: Top-Down 리포트 (모바일 가독성 차트/메트릭 위주)
    - [ ] `pages/2_Swing_Trading.py`: 스윙 추천 (카드 UI 활용, 테이블 컬럼 축소)
    - [ ] `pages/3_Trading_Journal.py`: 매매 일지 (입력 폼 간소화, 모바일 터치 친화적)

- [ ] **테스트 및 검증**
    - [ ] 전체 앱 실행 및 모바일 뷰 확인

