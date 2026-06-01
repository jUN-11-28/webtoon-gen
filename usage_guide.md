# WEBTOON GENERATOR USAGE GUIDE

# 기본 실행 구조

```bash
python scripts/generate_webtoon.py [JSON_PATH] [OPTIONS]
```

예시:

```bash
python scripts/generate_webtoon.py storyboards/positive_for_love/episode_01.json
```

---

# 주요 옵션

| 옵션                             | 설명               |
| ------------------------------ | ---------------- |
| `--all`                        | 모든 컷 생성          |
| `--importance high/medium/low` | 특정 중요도 컷만 생성     |
| `--start N`                    | N번째 컷부터 시작       |
| `--end N`                      | N번째 컷까지 생성       |
| `--limit N`                    | 최대 N컷만 생성        |
| `--with-text`                  | 말풍선/대사/SFX 포함 생성 |
| `--save-prompts`               | 사용된 프롬프트 txt 저장  |
| `--use-character-refs`         | 캐릭터 레퍼런스 이미지 사용  |
| `--use-scene-refs`             | 장면 레퍼런스 이미지 사용   |
| `--use-previous`               | 이전 컷 이미지를 참고     |
| `--output-dir PATH`            | 출력 폴더 지정         |
| `--model MODEL_NAME`           | 이미지 모델 지정        |
| `--size WIDTHxHEIGHT`          | 이미지 크기 지정        |

---

# 1. 말풍선 포함 1장 테스트

```bash
python scripts/generate_webtoon.py \
storyboards/positive_for_love/episode_01.json \
--limit 1 \
--with-text \
--save-prompts
```

---

# 2. 전체 컷 기준 11~13번 생성

```bash
python scripts/generate_webtoon.py \
storyboards/positive_for_love/episode_01.json \
--all \
--start 11 \
--end 13 \
--with-text \
--save-prompts
```

---

# 3. high 컷 기준 11번부터 3장 생성

```bash
python scripts/generate_webtoon.py \
storyboards/positive_for_love/episode_01.json \
--start 11 \
--limit 3 \
--with-text \
--save-prompts
```

---

# 4. 캐릭터 레퍼런스 사용

```bash
python scripts/generate_webtoon.py \
storyboards/positive_for_love/episode_01.json \
--start 11 \
--limit 3 \
--with-text \
--use-character-refs \
--save-prompts
```

---

# 5. 캐릭터 + 장면 레퍼런스 사용

```bash
python scripts/generate_webtoon.py \
storyboards/positive_for_love/episode_01.json \
--start 11 \
--limit 3 \
--with-text \
--use-character-refs \
--use-scene-refs \
--save-prompts
```

---

# 6. 캐릭터 + 장면 + 이전 컷까지 사용

```bash
python scripts/generate_webtoon.py \
storyboards/positive_for_love/episode_01.json \
--start 11 \
--limit 3 \
--with-text \
--use-character-refs \
--use-scene-refs \
--use-previous \
--save-prompts
```

이 방식이:

```txt
이전 컷 → 다음 컷
```

으로 자연스럽게 이어지는 가장 안정적인 방식이다.

---

# 추천 워크플로우

## 1단계 — 일부 컷 테스트

```bash
--limit 1
```

또는

```bash
--limit 3
```

으로 테스트.

---

## 2단계 — 캐릭터 고정

```bash
--use-character-refs
```

사용.

추천 구조:

```txt
references/characters/
├─ main_character.png
├─ villain.png
└─ side_character.png
```

---

# 3단계 — 장면 고정

```bash
--use-scene-refs
```

사용.

추천 구조:

```txt
references/scenes/
├─ S01.png
├─ S02.png
└─ S03.png
```

---

# 4단계 — 컷 연결 강화

```bash
--use-previous
```

사용.

이전 생성 컷을 자동으로 참고하여:

* 의상 유지
* 조명 유지
* 표정 흐름
* 포즈 흐름
* 카메라 방향

등을 자연스럽게 이어간다.

---

# 출력 위치

기본 출력 폴더:

```txt
tmp_images/
```

---

# 프롬프트 저장

```bash
--save-prompts
```

사용 시:

```txt
001_S01_C01_text.txt
```

형태로 저장된다.

프롬프트 수정 및 디버깅에 유용하다.

---

# 추천 생성 순서

## 테스트

```bash
--limit 1
```

↓

## 일부 컷 생성

```bash
--start 1 --end 5
```

↓

## continuity 수정

↓

## 전체 생성

```bash
--all
```

---

# 추천 레퍼런스 전략

## 가장 안정적인 방식

```txt
캐릭터 시트
+
장면 기준 이미지
+
이전 컷
```

조합.

---

# 레퍼런스 우선순위

```txt
1. character refs
2. scene refs
3. previous cut
```

순서로 영향력이 크다.

---

# 결과 파일 예시

```txt
tmp_images/
├─ 001_S01_C01_text.png
├─ 001_S01_C01_text.txt
├─ 002_S01_C02_text.png
└─ generation_results_text.json
```

---

# generation_results.json

생성 결과 기록 파일.

```json
[
  {
    "cut_order": 1,
    "cut_id": "S01_C01",
    "status": "success"
  }
]
```

---

# 추천 운영 방식

## 초기 테스트

```bash
--with-text
```

추천.

---

## 최종 제작

중요 컷은:

* 재생성
* 후편집
* 말풍선 수동 수정

권장.

---

# 참고

AI 텍스트 렌더링은 아직 완벽하지 않을 수 있다.

특히:

* 긴 대사
* 작은 말풍선
* 복잡한 효과음

은 깨질 수 있으므로:

```txt
컷당 대사 1~4줄
```

정도를 추천.



python scripts/generate_webtoon.py \
storyboards/how_we_become_human/episode_01.json \
--start 4 \
--with-text \
--use-character-refs \
--use-scene-refs \
--use-previous \
--save-prompts

python scripts/generate_webtoon.py \
storyboards/how_we_become_human/episode_02.json \
--all \
--with-text \
--use-character-refs \
--use-scene-refs \
--use-previous \
--save-prompts

# 1. 이미지 생성 (에피소드별 폴더 지정)
python scripts/generate_webtoon.py storyboards/how_we_become_human/episode_03.json \
  --all --workers 4 --with-text \
  --output-dir tmp_images/how_we_become_human/episode_03

python scripts/generate_webtoon.py storyboards/positive_for_love/episode_02_part_02.json \
  --all --workers 4 --with-text \
  --output-dir tmp_images/positive_for_love/episode_02_part_02

# 2. 카탈로그 업데이트 (새 이미지 생성 후 항상 실행)
python scripts/build_catalog.py