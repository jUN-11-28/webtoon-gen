# WEBTOON-GEN SETUP GUIDE

# 프로젝트 개요

이 프로젝트는 JSON 기반 웹툰 컷 콘티를 이용해 AI 이미지 생성 → Google Drive 자동 업로드까지 수행하는 자동화 시스템이다.

목표:

```txt
웹툰 JSON → 이미지 생성 → Google Drive 저장
```

사용 환경:

* GitHub Codespaces
* Python
* OpenAI Image API
* Google Drive API

---

# 프로젝트 구조

```txt
webtoon-gen/
├─ storyboards/
│  └─ positive_for_love/
│     └─ episode_01.json
│
├─ scripts/
│  └─ generate_webtoon.py
│
├─ tmp_images/
│
├─ outputs/
│
├─ .env
├─ .gitignore
├─ requirements.txt
└─ service_account.json
```

---

# 1. GitHub Repository 생성

Repository 이름:

```txt
webtoon-gen
```

---

# 2. GitHub Codespace 실행

GitHub Repository 접속

↓

```txt
Code
```

↓

```txt
Codespaces
```

↓

```txt
Create codespace on main
```

---

# 3. 필요한 패키지 설치

터미널 실행 후:

```bash
pip install openai python-dotenv google-api-python-client google-auth pillow
```

또는:

```bash
pip install -r requirements.txt
```

---

# 4. requirements.txt 생성

```txt
openai
python-dotenv
google-api-python-client
google-auth
pillow
```

---

# 5. Google Drive API 세팅

## 5-1. Google Cloud Console

접속:

https://console.cloud.google.com

---

## 5-2. 새 프로젝트 생성

프로젝트 이름:

```txt
webtoon-gen
```

---

## 5-3. Google Drive API 활성화

접속:

https://console.cloud.google.com/apis/library/drive.googleapis.com

↓

```txt
ENABLE
```

클릭

---

# 6. Service Account 생성

## 6-1. Credentials 페이지

https://console.cloud.google.com/apis/credentials

---

## 6-2. Create Credentials

```txt
+ CREATE CREDENTIALS
```

↓

```txt
Service Account
```

---

## 6-3. 서비스 계정 이름

예시:

```txt
webtoon-bot
```

↓

```txt
CREATE AND CONTINUE
```

↓

권한 설정 없이:

```txt
CONTINUE
```

↓

```txt
DONE
```

---

# 7. JSON 키 다운로드

서비스 계정 클릭

↓

```txt
KEYS
```

↓

```txt
ADD KEY
```

↓

```txt
Create new key
```

↓

```txt
JSON
```

↓

```txt
CREATE
```

다운로드 완료.

---

# 8. service_account.json 업로드

다운로드된 파일 이름 변경:

```txt
service_account.json
```

Codespace 루트에 업로드.

---

# 9. Google Drive 폴더 생성

Google Drive에서 폴더 생성:

예시:

```txt
webtoon-images
```

---

# 10. Google Drive 폴더 공유

service_account.json 내부:

```json
"client_email":
"webtoon-bot@webtoon-gen.iam.gserviceaccount.com"
```

이 이메일 복사.

↓

Google Drive 폴더 공유 설정

↓

해당 이메일 추가

↓

권한:

```txt
편집자
```

---

# 11. Google Drive Folder ID 복사

예시 URL:

```txt
https://drive.google.com/drive/folders/ABC123456
```

Folder ID:

```txt
ABC123456
```

---

# 12. .env 파일 생성

```env
OPENAI_API_KEY=YOUR_OPENAI_API_KEY
GOOGLE_DRIVE_FOLDER_ID=YOUR_DRIVE_FOLDER_ID
GOOGLE_SERVICE_ACCOUNT_FILE=service_account.json
```

---

# 13. .gitignore 생성

```gitignore
.env
service_account.json
tmp_images/
outputs/
__pycache__/
*.pyc
```

---

# 14. storyboard JSON 위치

예시:

```txt
storyboards/
└─ positive_for_love/
   └─ episode_01.json
```

---

# 15. 실행 방법

## 기본 실행 (high 컷만)

```bash
python scripts/generate_webtoon.py storyboards/positive_for_love/episode_01.json
```

---

## 일부만 테스트

```bash
python scripts/generate_webtoon.py storyboards/positive_for_love/episode_01.json --limit 3
```

---

## 전체 컷 생성

```bash
python scripts/generate_webtoon.py storyboards/positive_for_love/episode_01.json --all
```

---

## medium 컷만 생성

```bash
python scripts/generate_webtoon.py storyboards/positive_for_love/episode_01.json --importance medium
```

---

## 로컬 파일 유지

```bash
python scripts/generate_webtoon.py storyboards/positive_for_love/episode_01.json --keep-local
```

---

# 16. 결과 저장 위치

기본 구조:

```txt
tmp_images/
```

하지만 생성 후 자동 삭제됨.

최종 이미지는 Google Drive에 업로드됨.

---

# 17. generation_results.json

생성 결과 저장:

```json
[
  {
    "cut_id": "S01_C01",
    "drive_link": "...",
    "importance": "high"
  }
]
```

---

# 18. 비용 관련

## OpenAI

고퀄리티 / 감정 표현 우수

장당:
수십 원 ~ 수백 원 수준 가능

---

## Gemini

저렴함 / 대량 생성 유리

장당:
약 90~200원 수준

---

# 추천 전략

## 초안 생성

Gemini

↓

## 중요 컷 리파인

OpenAI

---

# 추천 워크플로우

```txt
스토리 작성
↓
컷 콘티 JSON 생성
↓
AI 이미지 생성
↓
Google Drive 저장
↓
Clip Studio 말풍선 작업
↓
웹툰 편집
```

---

# 향후 업그레이드 예정

* 캐릭터 얼굴 고정
* 참조 이미지 기반 생성
* 자동 말풍선 삽입
* 컷 자동 이어붙이기
* 웹툰 자동 배치
* SDXL / Flux 지원
* Gemini 지원
* 영상화 파이프라인
