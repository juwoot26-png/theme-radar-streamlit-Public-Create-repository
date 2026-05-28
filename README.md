# Theme Radar — US Stocks (Streamlit)

미국 주식 중심으로 매일 돈이 몰리는 섹터/테마/종목을 추천하는 개인용 웹앱(MVP).

## 로컬 실행
pip install -r requirements.txt
streamlit run app.py

## 배포 (Streamlit Cloud)
1) GitHub에 이 리포지토리를 푸시
2) [share.streamlit.io](https://share.streamlit.io) 에서 New app → 리포 선택 → app.py 지정 → Deploy
3) 생성된 URL을 북마크하고 사용

## 기능
- 섹터 쏠림: 대표 섹터 ETF의 1주/1개월 수익률과 거래량배수
- 오늘의 테마: 뉴스 빈도 기반 스코어
- 테마별 상위 종목: 거래량배수 + 모멘텀 기반 랭킹
- 종목 상세: 회사 개요, 간단 재무, 뉴스/SEC 링크
