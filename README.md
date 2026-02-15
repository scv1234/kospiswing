# 📈 주식 분석 대시보드 (Mobile Optimized)

모바일 환경에 최적화된 Streamlit 기반 주식 분석 및 매매 일지 앱입니다.

## 📱 주요 기능

### 1. Top-Down 리포트
- **지수/환율**: KOSPI, USD/KRW 실시간 지표 확인
- **섹터 수급**: 외국인/기관 순매수 상위 종목 및 섹터 차트
- **시장 메모**: 매크로 분석 코멘트 기록

### 2. 스윙 트레이딩 분석
- **알고리즘 추천**: 수급+기술+펀더멘털 분석 기반 TOP 3 종목 선정
- **카드 뷰**: 모바일에서 보기 편한 카드 형태의 추천 종목 정보
- **상세 데이터**: 목표가, 손절가, 추천 사유 제공

### 3. 매매 일지 (Trading Journal)
- **간편 입력**: 모바일에서도 쉽게 매매 기록 추가/수정
- **데이터 관리**: CSV 파일로 자동 저장 및 불러오기

---

## 🚀 실행 방법

### 1. 필수 라이브러리 설치
```bash
pip install -r requirements.txt
```

### 2. 앱 실행
```bash
streamlit run app.py
```

### 3. 모바일 접속
- **PC**: 브라우저에서 `http://localhost:8501` 접속
- **모바일**: PC와 같은 와이파이에 연결된 상태에서 `http://[PC IP 주소]:8501` 접속
  (실행 시 터미널에 표시되는 `Network URL` 확인)

---

## 📁 디렉토리 구조
```
stockanalysis/
├── app.py                  # 메인 앱 실행 파일
├── pages/                  # 페이지 파일
│   ├── 1_Daily_Top_Down.py
│   ├── 2_Swing_Trading.py
│   └── 3_Trading_Journal.py
├── utils/                  # 백엔드 로직
│   ├── data_fetcher.py     # 데이터 수집 (pykrx, FDR)
│   └── analysis.py         # 스윙 분석 알고리즘
├── data/                   # 데이터 저장소
│   └── trade_journal.csv   # 매매 일지 데이터
└── requirements.txt        # 의존성 파일
```
