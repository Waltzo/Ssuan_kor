# AGENT HANDOFF — ssuan_kor 프로젝트 인계 문서

이 파일은 **다음에 이 프로젝트를 이어 작업할 AI 에이전트(Claude / GPT-5.4 / 다른 모델)** 에게 보내는 핸드오프 문서다. 읽고 즉시 작업을 이어갈 수 있도록 구성됐다.

먼저 [PLAN.md](PLAN.md), [README.md](README.md), [AGENTS.md](AGENTS.md) 도 함께 참고. 이 파일은 그 셋의 **요약 + AI 작업용 컨텍스트**다.

---

## 0. TL;DR (3줄)

- **무엇**: 작혼(MahjongSoul) Windows 오버레이 — 인게임 화면 캡처 → 패 인식 → 리치 마작 결정 보조 (타패/리치/오시히키/위험패 등)
- **어디까지**: 분석 엔진 + 인식 PoC + 라이브 모드 + PyInstaller spec 완성. **77/77 테스트 통과.**
- **남은 것**: 사용자 본인 환경(Windows 1920x1080)서 인게임 템플릿 라벨링 → 라이브 실측 → 빌드.

---

## 1. 사용자 환경 — 필수 인지 사항

### 1.1 Caveman 모드 활성

사용자는 **caveman 모드(full 레벨)** 를 켜고 작업한다. 응답 규칙:

- 관사(the/a/an) 드롭, 군더더기(just/really/basically/actually/simply) 드롭, 인사말(certainly/of course/happy to) 드롭, 헷지 드롭
- 단편(fragment) OK. 짧은 동의어 우선 (`fix` not "implement a solution for")
- 기술 용어 정확. 코드/에러 메시지 변경 금지
- 패턴: `[thing] [action] [reason]. [next step].`
- **예외(평문 유지)**: 보안 경고, 되돌릴 수 없는 작업 확인, 다단계 순서 모호 위험, 사용자 명시 요구
- **코드/커밋/PR 본문은 항상 평문**. caveman은 채팅 응답에만 적용

**계속 활성**. 사용자가 "stop caveman" / "normal mode" 하기 전엔 끄지 말 것.

### 1.2 사용자 컨텍스트

- 한국어 사용. 응답·문서 모두 한국어
- 작업 디렉토리: `/home/rns/jkjung/ssuan_kor` (Linux WSL/Ubuntu 추정)
- **개발 환경 = Linux**, **실행 대상 = Windows**. 캡처·오버레이 코드는 Linux서 import는 OK이나 실 동작은 Windows 필요
- Python 3.13 사용 중

---

## 2. 결정된 사항 (변경 금지)

| 항목 | 결정 | 이유 |
|---|---|---|
| 룰 | 리치 마작 (일본식) | 사용자 선택 |
| 대상 클라이언트 | 작혼 (MahjongSoul, 한국 서버 추정) | 사용자 선택 |
| 입력 방식 | 화면 캡처 + 패 인식 | 사용자 선택 |
| 언어/스택 | Python 3.11+, mahjong lib, OpenCV, PyQt6, dxcam/mss, pywin32 | 사용자 선택 |
| 분석 레이어 OS 의존 | **무관** (GameState만 입력) | 테스트 가능성 + Linux 개발 환경 |
| 라이브러리 | `mahjong>=2.0` (PyPI) — 샹텐·HandCalculator | 신뢰성 |

설계 철학: **"보여주는 툴"이 아니라 "결정해주는 툴"**. 샹텐·우케이레 표시는 플레이어가 이미 앎. 진짜 가치는 타패 추천/후리텐 경고/오시히키 판단 같은 결정 보조.

---

## 3. 아키텍처

```
[작혼 창]
   │ win32gui (WindowTracker)
   ▼
[CaptureLoop]  별도 스레드, fps 기반, dxcam → 프레임 dedup (md5)
   │ frame
   ▼
[Recognition Layer]
   profile.py (비율 좌표) → slicer.py → matcher.py (멀티스케일 + CLAHE)
   theme.py (사용자 스킨별 템플릿)
   │ tiles[], confs[]
   ▼
[Analysis Engine]
   GameState ▶ shanten / efficiency / tenpai / value / yaku_suggest /
              danger / push_fold / riichi_decide / call_decide /
              opp_yaku / standings
   │ DiscardOption / TenpaiInfo / DangerReport / PushFoldAdvice / ...
   ▼ pyqtSignal (스레드 안전)
[Overlay UI]
   PyQt6 frameless / translucent / always-on-top / 클릭 통과
   드래그 이동, 입력란 (CLI 명령 재사용), 출력 패널
```

**핵심 원칙**: 분석 레이어는 GameState 한 자료구조에만 의존. 인식·오버레이와 완전 분리. → 분석은 Linux서 단위 테스트로 100% 검증, 인식·UI는 별도로 개선.

---

## 4. 모듈 인벤토리

### `src/core/`
- `game_state.py` — `Tile`, `Meld`, `Discard`, `Seat`, `Wind`, `MeldType`, `RoundInfo`, `GameState` (frozen dataclasses)

### `src/analysis/` (전부 OS 무관, GameState만 입력)
- `_libbridge.py` — mahjong 라이브러리 변환 (모든 lib 의존을 한 곳에 모음). **아카 슬롯 회피 가드** (4.1 함정 참조)
- `tiles.py` — 패 변환 (34/136-array), 보이는 패 계수, `parse_hand`
- `shanten.py` — 일반/치또이/국사 샹텐
- `efficiency.py` — 우케이레 + **타패 추천** (`recommend_discards`)
- `tenpai.py` — 대기패 / 후리텐 / 役なし / 리치 가능
- `value.py` — 타점 추정 (도라·아카·우라·리치)
- `yaku_suggest.py` — 역 추천 (탕야오·역패·혼/청일색·치또이·또이또이·핑후 휴리스틱)
- `danger.py` — 위험패 (현물·중/편스지·노찬스·원찬스·字牌·도라위험)
- `push_fold.py` — 오시히키 (밀기/접기/중립)
- `riichi_decide.py` — 리치/다마텐/비추천
- `call_decide.py` — 부로 콜/스킵
- `opp_yaku.py` — 상대 역 예측 (버림패·부로 패턴)
- `standings.py` — 점수상황·착순 모드

### `src/recognition/` (인식 레이어)
- `profile.py` — 비율 좌표 프로파일 + YAML 로드/저장
- `slicer.py` — 영역 크롭 + 손패 슬롯 균등 분할 (정수 분할로 ±1px 균일)
- `theme.py` — 테마(스킨)별 템플릿 디렉토리 로드
- `matcher.py` — 멀티스케일 템플릿 매칭 + grayscale + CLAHE 정규화
- `__init__.py` — `recognize_my_hand(image, profile, theme)` 진입점

### `src/capture/` (Windows 의존, Linux서 None 반환 stub)
- `window_finder.py` — `find_mahjongsoul_window()` (win32gui)
- `screen_capture.py` — `ScreenCapture` (dxcam → mss 폴백)
- `window_tracker.py` — `WindowTracker.poll()` 변경 감지 콜백
- `capture_loop.py` — `CaptureLoop` 별도 스레드, fps, 프레임 dedup
- `recognition_worker.py` — 추적+캡처+인식 통합

### `src/cli/`
- `manual.py` — 수동 입력 REPL (`run_manual_cli`). `handle_command()` 는 오버레이서도 재사용. **모든 분석 기능 호출 통합**

### `src/overlay/`
- `window.py` — `OverlayWindow`. 기본 모드 + `enable_live(theme)` 라이브 모드 (pyqtSignal로 워커 → UI 마샬링)

### `tools/`
- `preview_profile.py` — 프로파일 좌표 시각화 (캘리브레이션)
- `collect_templates.py` — 인게임 캡처서 슬롯 라벨링 → 테마 템플릿 추출 (**진짜 매칭에 필수**)
- `extract_grid.py` — 도감 grid 시트(hand_2/4 같은) 자동 추출. **인식 정확도엔 부적합** (환경 다름) — UI 아이콘용
- `build_exe.py` — PyInstaller 빌드 진입점 (`--clean`, `--onefile`)

### 설정·자료
- `config/profiles/default_16x9.yaml` — 기본 좌표 프로파일 (비율 기반, 추정값. 사용자 환경에 맞춰 미세조정 필요)
- `config/layouts/hand_2.yaml`, `hand_4.yaml` — 도감 grid 추출용 (생성 완료, 결과: `assets/templates/cat_fish/`, `cat_whirl/`)
- `assets/templates/<theme>/` — 패 템플릿 PNG (각 테마 ~37개)
- `ssuan_kor.spec` — PyInstaller 빌드 spec
- `requirements.txt` — 의존성

### 진입점
- `main.py` — `--phase0` / `--manual` / `--overlay [--live --theme <name>]`

### 테스트
- `tests/test_analysis.py` — 핵심 샹텐·타패·후리텐
- `tests/test_value_and_yaku.py` — 타점·역 추천
- `tests/test_danger.py` — 위험패
- `tests/test_push_fold.py` — 오시히키
- `tests/test_phase3.py` — 리치/부로/상대역/점수
- `tests/test_recognition.py` — 프로파일·슬라이서
- `tests/test_capture_workers.py` — 윈도우추적·캡처루프 (mocking)

`python -m pytest tests/ -q` → **77 passed**

### 문서
- `README.md` — 사용자용 (설치·실행·CLI 명령·데모·인식 절차·빌드·현황)
- `PLAN.md` — 설계·로드맵·진행 현황 (체크리스트)
- `AGENTS.md` — 모듈 의존 그래프·라이브러리 함정·튜닝 포인트
- `AGENT_HANDOFF.md` — **이 파일** (다음 AI 에이전트용)

---

## 5. 알려진 함정 (반드시 알 것)

### 5.1 아카 슬롯 함정 (해결됨, 가드 유지 필수)

mahjong 라이브러리는 136-index `16` (5m), `52` (5p), `88` (5s) 를 **아카로 자동 인식**. 일반 5m/p/s를 그 슬롯에 배치하면 라이브러리가 아카로 오인 → 도라 오계산 → 타점 부풀림 (만관 거짓 표시).

**가드 위치**: `src/analysis/_libbridge.py` — `hand_and_win_136`, `tiles.py:tiles_to_136` 둘 다 아카 슬롯 회피.

→ 이 부분 절대 건드리지 말 것. 새 변환 함수 추가 시 같은 회피 적용.

### 5.2 Reference sheet ↔ 인게임 환경 mismatch

도감 시트 (`hand_0.png`, `hand_2.png`, `hand_4.png`)서 자동 추출한 템플릿은 **인게임 화면 인식엔 거의 동작 안 함** (실측 0/14). 이유: 도감은 흰배경·정면·큰사이즈, 인게임은 어두운배경·살짝기울임·작은사이즈.

→ **인게임 캡처서 직접 라벨링 (`tools/collect_templates.py`)** 만이 정확도를 보장. 같은 환경 매칭은 14/14 (1.00) 검증됨.

### 5.3 다운스케일 사진은 정확도 ↓

SNS 업로드된 다운스케일 이미지(예: 955x537)는 작혼 데스크톱 원본(1920x1080)과 패 그래픽 비율 다름 → 멀티스케일 매칭도 한계. **사용자에게 1920x1080 PNG 원본 캡처 요청** 권장.

### 5.4 좌표 프로파일 — 환경별 미세조정

`config/profiles/default_16x9.yaml`은 **추정값**. 사용자 환경(해상도·UI 스케일·창 크기)에 따라 손패 영역 위치가 다를 수 있음. → `python tools/preview_profile.py <캡처>` 로 시각 확인 후 YAML 직접 편집.

### 5.5 PyInstaller — OS 의존 빌드

PyInstaller는 **빌드 OS의 바이너리만** 만든다. Linux서 빌드하면 ELF (Windows 사용자에게 무용). Windows .exe는 Windows에서 빌드 필수.

### 5.6 Linux서 win32gui 미존재

`src/capture/window_finder.py` 는 `sys.platform == "win32"` 가드로 Linux서 win32 import 회피. Linux서 `find_mahjongsoul_window()` 항상 `None` 반환. 캡처 워커들도 region=None 시 grab 호출 안 함. **Linux 테스트는 mocking 사용** (`tests/test_capture_workers.py` 참고).

### 5.7 PyQt 스레드 — 시그널 마샬링 필수

`CaptureLoop` 콜백은 **별도 스레드**에서 발화. UI 위젯 직접 변경하면 크래시. `OverlayWindow` 는 `pyqtSignal` 로 메인 스레드 마샬링. 새 기능 추가 시 같은 패턴 적용.

### 5.8 작혼 약관 — 회색지대

화면 캡처 오버레이는 입력 자동화 아님 → 회색지대. 사용자 약관 명시: "개인 학습용". **자동 클릭/메모리 조작 절대 추가 금지**. 공개 배포 권장 안 함.

---

## 6. 코딩 규약

- **`from __future__ import annotations`** 전 파일 (postponed annotations)
- **Frozen dataclass** 우선 (불변, 해시 가능)
- **한국어 docstring + 인라인 주석** (사용자 언어 일치)
- **타입 힌트** 모든 public API
- **mahjong 라이브러리 의존** → `_libbridge.py`에 모음 (다른 모듈서 직접 import 금지)
- **캡처/UI 신코드** → `pyqtSignal`로 스레드 마샬링
- **새 분석 모듈** → GameState만 입력으로, OS 무관 유지
- **테스트** → 분석은 직접 검증, 인식/캡처는 mocking

---

## 7. 진행 현황 (요약)

| Phase | 상태 |
|---|---|
| Phase 0 (캡처 PoC) | 코드 ✓, Windows 실측 대기 |
| Phase 1 분석 (샹텐·타패·후리텐·役なし·타점·역추천) | ✓ |
| Phase 2 분석 (위험패·베타오리) | ✓ |
| Phase 3 분석 (오시히키·리치·부로·상대역·점수) | ✓ |
| 수동 입력 CLI | ✓ (`--manual`) |
| 오버레이 UI 셸 | ✓ (`--overlay`) |
| 인식 PoC (좌표·매칭·테마·도구) | ✓ |
| 자동 추적 + 실시간 캡처 + 라이브 인식 | ✓ (`--overlay --live`) |
| PyInstaller spec + 빌드 스크립트 | ✓ |
| **테스트** | **77/77 통과** |

---

## 8. 다음 작업 후보 (우선순위)

### 8.1 사용자 액션 필요 (코드 작업 X)

| 액션 | 산출 |
|---|---|
| Windows 1920x1080 작혼 캡처 5~10장 (친선전 vs AI 또는 리플레이, 다양한 패) | 인게임 템플릿 추출 자료 |
| `python tools/collect_templates.py` 반복 | 사용자 테마 (37종) |
| `python tools/preview_profile.py` 후 좌표 보정 | `config/profiles/<해상도>.yaml` |
| `python main.py --overlay --live --theme <name>` 실측 | 라이브 모드 검증 |
| `python tools/build_exe.py --onefile` (Windows) | `dist/ssuan_kor.exe` |

### 8.2 코드 작업 (필요 시)

| 작업 | 설명 |
|---|---|
| 다해상도 강건성 | 프로파일 자동 매칭 (해상도별), feature-based 매칭 (ORB/SIFT) |
| 좌표 캘리브레이션 GUI | YAML 수동 편집 대신 마우스 드래그로 영역 조정 |
| 테다시/쯔모기리 인식 | 상대 텐파이 추정 정밀화 (PLAN.md 4.2 참조) |
| 4인 버림패·부로·도라표시패 영역 인식 | 현재는 my_hand만. 프로파일 확장 필요 |
| 오버레이 패널 분리 | 현재 단일 텍스트. 위험패는 색상 바, 타패는 카드 등 시각화 |
| 점수·순목 OCR | 현재 수동 입력. 텍스트 영역 OCR (Tesseract) |
| 부로 자동 감지 → 부로 판단 자동 발화 | 상대가 패 버린 직후 트리거 |
| 학습 모델 | 템플릿 매칭 한계 시 YOLO/CNN 도입 (`models/` 디렉토리 예약됨, 비어 있음) |

### 8.3 미루어진 사항

- `hand_0.png` (기본 작혼 스킨) 자동 추출 — layout 불규칙해 grid 자동화 안 됨. 수동 라벨링 필요
- 우라스지·걸침스지 정밀 분류 — 현재 위험패는 중스지/편스지만 구분
- 사안차·삼안차 등 더 많은 역 휴리스틱
- 깡도라/우라도라 자동 처리 (`value.py`는 인자로 받지만 라이브 인식엔 미통합)

---

## 9. 사용자 환경 / 캡처 가이드 (사용자에게 안내할 것)

### 9.1 캡처 권장
- 작혼 데스크톱 1920x1080 창 모드 (전체화면 독점 X — 오버레이 가려짐)
- **친선전 vs AI** 또는 **리플레이** (게임 엔진 동일)
- PNG 원본 (다운스케일 X)

### 9.2 NG (안 됨)
- 도감/일람표 (다른 환경)
- SNS 다운스케일 사진
- 모바일판 캡처 (UI 비율 다름)

### 9.3 인식 셋업 절차
1. 캡처 1장 → `python tools/preview_profile.py <img>` → 좌표 확인 → YAML 편집
2. 같은 캡처 → `python tools/collect_templates.py <img> mytheme` → 슬롯 라벨링
3. 다른 캡처 시도 → `python main.py --manual` → `recognize <img2> mytheme`
4. 정확도 OK이면 → `python main.py --overlay --live --theme mytheme`

---

## 10. 환경 / 의존성

```
Python 3.11+
mahjong>=2.0
opencv-python>=4.9
PyQt6>=6.6
numpy, Pillow, PyYAML, pydantic, pytest
dxcam>=0.0.5  ; Windows
mss>=9.0
pywin32>=306  ; Windows
pyinstaller   ; (선택) 빌드용
```

설치: `pip install -r requirements.txt`

---

## 11. 즉시 사용 가능한 명령

```bash
# 테스트
python -m pytest tests/ -q

# 수동 입력 모드 (분석만)
python main.py --manual
> 234567m234567p5s
> riichi s
> oppdiscard s 1m5m9p2z

# 오버레이 (수동)
python main.py --overlay

# 오버레이 라이브 (Windows + 사용자 테마 추출 후)
python main.py --overlay --live --theme mytheme --fps 2

# 좌표 캘리브레이션
python tools/preview_profile.py screenshot.png

# 템플릿 추출 (인게임)
python tools/collect_templates.py screenshot.png mytheme

# 도감서 추출 (UI 아이콘용 — 인식 정확도엔 부적합)
python tools/extract_grid.py config/layouts/hand_2.yaml cat_fish

# 빌드 (Windows)
pip install pyinstaller
python tools/build_exe.py --onefile
```

---

## 12. 이 문서를 받은 AI에게

1. 이 파일 + `PLAN.md` + `README.md` + `AGENTS.md` 먼저 읽기
2. **caveman 모드** 켤 것 (사용자가 켜고 작업)
3. 한국어로 응답
4. 변경 전 `python -m pytest tests/ -q` → 77 passed 확인
5. 변경 후 다시 테스트 → 통과 유지
6. 분석 레이어 작업 시 `_libbridge.py` 함정(아카 슬롯) 절대 건드리지 말 것
7. 새 모듈 추가 시 `tests/`에 테스트 함께 작성
8. UI 작업 시 `pyqtSignal` 마샬링 패턴 따를 것
9. 빌드 (.exe) 변경 시 `ssuan_kor.spec` `datas`/`hiddenimports` 확인
10. 인식 정확도 의심 시 → reference sheet 보지 말고 **인게임 캡처 추출** 강조 권장
