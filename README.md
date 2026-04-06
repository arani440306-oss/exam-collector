# 📄 전국 중학교 시험지 수집 캠페인

> 전국 중학교 시험지를 학교·학년·과목별로 선착순 수집하는 모바일 친화적 웹 캠페인 앱

---

## 🎯 기획 의도

학생들이 직접 찍은 시험지를 온라인으로 간편하게 제출하고, 소정의 상품(네이버페이 포인트)을 받을 수 있는 **시험지 수집 이벤트 플랫폼**입니다.

- 전국 중학교 × 3개 학년 × 12개 과목을 독립적으로 수집
- **선착순 1명만** 제출 가능 (학교 + 학년 + 과목 단위 중복 방지)
- Claude AI Vision으로 시험지 여부를 자동 검증하여 어뷰징 방지
- 관리자는 실시간으로 수집 현황을 모니터링

---

## ✨ 주요 기능

| 기능 | 설명 |
|------|------|
| 📍 단계별 선택 | 시도 → 구군 → 학교 → 학년 → 과목 순으로 선택 |
| 🚩 선착순 마감 | 이미 제출된 학교·학년·과목은 SOLD OUT 표시 |
| 🤖 AI 검증 | Claude Vision API로 시험지 여부 자동 판별 |
| 📸 다중 업로드 | 여러 장 동시 선택 및 미리보기 지원 |
| 🎁 상품 신청 | 제출 후 휴대전화번호 입력으로 기프티콘 신청 |
| 📋 관리자 페이지 | 실시간 제출 현황 및 지역별 통계 확인 |
| 📱 QR 코드 | 오프라인 배포용 QR 코드 자동 생성 |

---

## 🖥️ 화면 구성

```
웰컴 화면 → 시도 선택 → 구군 선택 → 학교 선택
         → 학년 선택 → 과목 선택 → 시험지 업로드
         → (AI 검증) → 성공 / SOLD OUT
         → 전화번호 입력 → 완료
```

---

## 🚀 설치 및 실행

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 서버 실행

```bash
python main.py
```

또는 Windows 환경에서:

```bash
run.bat
```

서버가 시작되면 브라우저에서 접속:

- **메인 페이지:** http://localhost:8000
- **관리자 페이지:** http://localhost:8000/admin
- **QR 코드 생성:** http://localhost:8000/qr?host=내_IP:8000

---

## 🤖 Claude AI 검증 설정 (선택)

환경변수에 Anthropic API 키를 설정하면 시험지 여부를 AI로 자동 검증합니다.  
설정하지 않으면 검증을 건너뛰고 모든 이미지를 통과시킵니다.

```bash
# Windows
set ANTHROPIC_API_KEY=your_api_key_here

# macOS / Linux
export ANTHROPIC_API_KEY=your_api_key_here
```

---

## 📡 외부 공유 (ngrok)

로컬 서버를 인터넷에 임시 공개하려면 [ngrok](https://ngrok.com)을 사용하세요.

```bash
ngrok http 8000
```

출력된 `https://xxxx.ngrok-free.app` 주소를 공유하면 누구나 접속할 수 있습니다.

---

## 🗂️ 프로젝트 구조

```
exam_collector/
├── main.py                  # FastAPI 서버 (API + 라우팅)
├── requirements.txt         # Python 의존성
├── run.bat                  # Windows 실행 스크립트
├── 전국_중학교_목록.json       # 전국 중학교 데이터
├── templates/
│   ├── index.html           # 메인 수집 페이지 (모바일 UI)
│   ├── admin.html           # 관리자 현황 페이지
│   └── qr.html              # QR 코드 페이지
├── uploads/                 # 업로드된 시험지 이미지 저장
└── static/                  # 정적 파일 (QR 이미지 등)
```

---

## 🛠️ 기술 스택

- **Backend:** Python 3.12, FastAPI, SQLite
- **Frontend:** Vanilla JS, HTML/CSS (모바일 퍼스트)
- **AI:** Claude Haiku (Anthropic Vision API)
- **이미지 처리:** Pillow (리사이즈 + JPEG 최적화)
- **QR 코드:** qrcode 라이브러리

---

## 📌 참고사항

- 학교당 최대 수집 슬롯: **36개** (3학년 × 12과목)
- 이미지 최대 크기: **30MB** / 자동으로 2400px 이하로 리사이즈
- DB 파일(`exam_collector.db`)과 업로드 이미지는 `.gitignore`로 제외됨
