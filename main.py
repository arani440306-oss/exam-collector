"""
전국 중학교 시험지 수집 웹앱
- 지역 > 학교 > 학년 > 과목 선택 후 시험지 이미지 업로드 (복수 파일)
- 학교+학년+과목 중복 제출 방지 (SOLD OUT)
- Claude Vision API로 시험지 여부 검증
- 성공 후 상품 수령 전화번호 + 개인정보 동의 등록
"""

import asyncio
import base64
import io
import json
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import List

import qrcode
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image

# ---------------------------------------------------------------------------
# 경로 설정
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# 학교 데이터 로드
# ---------------------------------------------------------------------------
SCHOOL_JSON = BASE_DIR.parent / "전국_중학교_목록.json"
with open(SCHOOL_JSON, encoding="utf-8") as f:
    _raw = json.load(f)

SCHOOL_INDEX: dict[str, dict[str, list[dict]]] = {}
for s in _raw:
    sido = s.get("sido_nm", "")
    gugun = s.get("gugun_nm", "")
    SCHOOL_INDEX.setdefault(sido, {}).setdefault(gugun, []).append(s)

SIDO_ORDER = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
              "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]
SIDO_LIST = [s for s in SIDO_ORDER if s in SCHOOL_INDEX]

SUBJECTS = ["국어", "수학", "영어", "과학", "사회", "역사", "도덕",
            "기술·가정", "음악", "미술", "체육", "정보"]

# 학교당 최대 슬롯 수 (3학년 × 12과목)
MAX_SLOTS = 3 * len(SUBJECTS)

# ---------------------------------------------------------------------------
# DB 초기화
# ---------------------------------------------------------------------------
DB_PATH = BASE_DIR / "exam_collector.db"


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id          TEXT PRIMARY KEY,
                sido_nm     TEXT NOT NULL,
                gugun_nm    TEXT NOT NULL,
                school_code TEXT NOT NULL,
                school_nm   TEXT NOT NULL,
                grade       INTEGER NOT NULL,
                subject     TEXT NOT NULL,
                image_paths TEXT NOT NULL,
                phone       TEXT,
                created_at  TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_no_dup
            ON submissions(school_code, grade, subject)
        """)


init_db()

# ---------------------------------------------------------------------------
# Claude Vision: 시험지 여부 확인
# ---------------------------------------------------------------------------
async def check_is_exam_paper(image_data: bytes, content_type: str) -> bool:
    """
    ANTHROPIC_API_KEY 환경변수가 없으면 검사를 생략하고 True 반환.
    Claude Haiku로 시험지(문제지) 여부를 판별.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return True

    def _call():
        import anthropic  # 런타임 임포트 (선택적 의존성)
        client = anthropic.Anthropic(api_key=api_key)
        safe_type = content_type if content_type in (
            "image/jpeg", "image/png", "image/gif", "image/webp"
        ) else "image/jpeg"
        b64 = base64.standard_b64encode(image_data).decode()
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image",
                     "source": {"type": "base64", "media_type": safe_type, "data": b64}},
                    {"type": "text",
                     "text": (
                         "이 이미지가 학교 시험지(시험 문제지 또는 답안지)인가요? "
                         "'yes' 또는 'no'로만 답하세요."
                     )},
                ],
            }],
        )
        return "yes" in msg.content[0].text.strip().lower()

    try:
        return await asyncio.to_thread(_call)
    except Exception:
        return True  # 오류 시 통과


# ---------------------------------------------------------------------------
# FastAPI 앱
# ---------------------------------------------------------------------------
app = FastAPI(title="시험지 수집 캠페인")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


# ---------------------------------------------------------------------------
# 페이지 라우트
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request):
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT id, sido_nm, gugun_nm, school_nm, grade, subject, "
            "image_paths, phone, created_at "
            "FROM submissions ORDER BY created_at DESC"
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
        by_sido = conn.execute(
            "SELECT sido_nm, COUNT(*) FROM submissions GROUP BY sido_nm ORDER BY 2 DESC"
        ).fetchall()

    submissions = []
    for r in rows:
        try:
            paths = json.loads(r[6]) if r[6].startswith("[") else [r[6]]
        except Exception:
            paths = [r[6]]
        submissions.append({
            "id": r[0], "sido_nm": r[1], "gugun_nm": r[2], "school_nm": r[3],
            "grade": r[4], "subject": r[5], "image_paths": paths,
            "phone": r[7] or "미입력", "created_at": r[8],
        })

    return templates.TemplateResponse("admin.html", {
        "request": request,
        "submissions": submissions,
        "total": total,
        "by_sido": by_sido,
    })


@app.get("/qr", response_class=HTMLResponse)
async def qr_page(request: Request, host: str = "localhost:8000"):
    url = f"http://{host}"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_path = STATIC_DIR / "qr_code.png"
    qr_img.save(str(qr_path))
    return templates.TemplateResponse("qr.html", {
        "request": request,
        "url": url,
        "ts": int(datetime.now().timestamp()),
    })


# ---------------------------------------------------------------------------
# API 라우트
# ---------------------------------------------------------------------------
@app.get("/api/sido")
async def api_sido():
    return SIDO_LIST


@app.get("/api/gugun")
async def api_gugun(sido: str):
    guguns = SCHOOL_INDEX.get(sido)
    if guguns is None:
        raise HTTPException(404, "시도를 찾을 수 없습니다")
    return sorted(guguns.keys())


@app.get("/api/schools")
async def api_schools(sido: str, gugun: str):
    schools = SCHOOL_INDEX.get(sido, {}).get(gugun)
    if schools is None:
        raise HTTPException(404, "구군을 찾을 수 없습니다")

    # 제출 건수가 있는 학교 코드 조회
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT school_code, COUNT(*) FROM submissions GROUP BY school_code"
        ).fetchall()
    submitted_cnt = {r[0]: r[1] for r in rows}

    result = []
    for s in schools:
        code = s["SHL_CD"]
        cnt = submitted_cnt.get(code, 0)
        result.append({
            "code": code,
            "name": s["SHL_NM"],
            # 모든 슬롯(3학년 × 12과목)이 가득 찬 경우만 완전 마감
            "sold_out": cnt >= MAX_SLOTS,
            # 1건이라도 제출된 경우 부분 마감 표시
            "has_any": cnt > 0,
        })

    return sorted(result, key=lambda x: x["name"])


@app.get("/api/soldout")
async def api_soldout(school_code: str, grade: int):
    """해당 학교+학년에서 이미 제출된 과목 목록 반환"""
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT subject FROM submissions WHERE school_code=? AND grade=?",
            (school_code, grade),
        ).fetchall()
    return [r[0] for r in rows]


@app.post("/api/check-image")
async def api_check_image(image: UploadFile = File(...)):
    """AI로 시험지 여부만 확인 (저장 없음)"""
    data = await image.read()
    if len(data) > 30 * 1024 * 1024:
        raise HTTPException(400, "파일이 너무 큽니다")
    is_exam = await check_is_exam_paper(data, image.content_type or "image/jpeg")
    return {"is_exam": is_exam}


@app.post("/api/upload")
async def api_upload(
    school_code: str = Form(...),
    school_nm: str = Form(...),
    sido_nm: str = Form(...),
    gugun_nm: str = Form(...),
    grade: int = Form(...),
    subject: str = Form(...),
    images: List[UploadFile] = File(...),
):
    if not images:
        raise HTTPException(400, "이미지를 선택해주세요")

    # 중복 확인 (선착순)
    with sqlite3.connect(DB_PATH) as conn:
        dup = conn.execute(
            "SELECT id FROM submissions WHERE school_code=? AND grade=? AND subject=?",
            (school_code, grade, subject),
        ).fetchone()
    if dup:
        return JSONResponse({"success": False, "reason": "sold_out"}, status_code=409)

    saved_filenames = []
    for img_file in images:
        ct = img_file.content_type or ""
        if not ct.startswith("image/"):
            raise HTTPException(400, "이미지 파일만 업로드 가능합니다")
        data = await img_file.read()
        if len(data) > 30 * 1024 * 1024:
            raise HTTPException(400, "파일 크기는 30MB 이하여야 합니다")
        try:
            img = Image.open(io.BytesIO(data)).convert("RGB")
            if max(img.size) > 2400:
                img.thumbnail((2400, 2400), Image.LANCZOS)
            filename = f"{uuid.uuid4().hex}.jpg"
            img.save(str(UPLOAD_DIR / filename), "JPEG", quality=88, optimize=True)
            saved_filenames.append(filename)
        except Exception as exc:
            raise HTTPException(400, f"이미지 처리 오류: {exc}") from exc

    sub_id = uuid.uuid4().hex
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO submissions VALUES (?,?,?,?,?,?,?,?,?,?)",
                (sub_id, sido_nm, gugun_nm, school_code, school_nm,
                 grade, subject, json.dumps(saved_filenames),
                 None, datetime.now().isoformat()),
            )
    except sqlite3.IntegrityError:
        for fn in saved_filenames:
            try:
                os.remove(UPLOAD_DIR / fn)
            except OSError:
                pass
        return JSONResponse({"success": False, "reason": "sold_out"}, status_code=409)

    return {"success": True, "id": sub_id}


@app.post("/api/phone")
async def api_phone(submission_id: str = Form(...), phone: str = Form(...)):
    digits = phone.replace("-", "").replace(" ", "")
    if not (digits.isdigit() and 10 <= len(digits) <= 11):
        raise HTTPException(400, "올바른 휴대전화번호를 입력해주세요")

    formatted = (
        f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
        if len(digits) == 11
        else f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    )

    with sqlite3.connect(DB_PATH) as conn:
        res = conn.execute(
            "UPDATE submissions SET phone=? WHERE id=?",
            (formatted, submission_id),
        )
        if res.rowcount == 0:
            raise HTTPException(404, "제출 정보를 찾을 수 없습니다")

    return {"success": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        reload=True,
    )
