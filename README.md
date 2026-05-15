# ssuan_kor — 작혼 리치 마작 오버레이 어시스턴트

작혼(MahjongSoul) 위에 떠서 실시간 리치 마작 조언을 제공하는 Windows용 오버레이 프로그램.

> **설계 철학**: "보여주는 툴"이 아니라 **"결정해주는 툴"**.
> 샹텐·우케이레는 플레이어가 이미 안다. 진짜 가치는 타패 추천 / 후리텐 경고 /
> 오시히키 판단처럼 **결정 보조**에 있다.

설계 상세는 [PLAN.md](PLAN.md) 참조.

---

## 요구 환경

- **Windows** (캡처·오버레이 기능에는 Windows 전용 API 사용 — `pywin32`, `dxcam`)
- Python 3.11+
- 분석 엔진·CLI는 **OS 무관** — Linux/macOS에서도 동작·검증 가능
- 작혼은 **창 모드**로 실행 권장 (전체화면 독점 모드는 오버레이가 가려짐)

## 설치

```bash
python -m venv .venv
.venv\Scripts\activate     # (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
```

## 실행 모드

### 1. 수동 입력 CLI (`--manual`) — 인식 레이어 불필요

패를 직접 입력해 분석 엔진을 즉시 사용. 인식 모듈 없이도 모든 분석 기능 동작.

```bash
python main.py --manual
```

### 2. 오버레이 모드 (`--overlay`) — PyQt6 투명 창

작혼 위에 띄우는 frameless / translucent / always-on-top 창.

**기본 모드** — 명령 입력으로 수동 분석:
```bash
python main.py --overlay
```

**라이브 모드** — 작혼 창 자동 추적 + 실시간 인식 + 자동 분석 (Windows):
```bash
python main.py --overlay --live --theme mytheme [--fps 2.0]
```

| 키 | 동작 |
|---|---|
| 드래그 | 창 이동 |
| F8 | 클릭 통과 모드 토글 (Windows 한정) |
| F2 / F3 | 투명도 ↑ / ↓ |
| Esc | 종료 |

라이브 모드 동작:
1. `WindowTracker` 가 작혼 창 위치를 300ms 간격으로 폴링
2. `CaptureLoop` 가 별도 스레드서 fps 간격 캡처 + 프레임 dedup
3. 변경 프레임마다 `recognize_my_hand` → 결과를 Qt 시그널로 메인 스레드 마샬링
4. 손패 자동 갱신 + 분석 재실행

### 3. Phase 0 캡처 PoC (`--phase0`) — Windows 한정

작혼 창을 찾아 클라이언트 영역을 캡처하고 `debug/phase0_capture.png`에 저장.

```bash
python main.py --phase0
```

---

## CLI 명령 레퍼런스

### 손패 / 게임 상태

| 명령 | 설명 |
|---|---|
| `<패표기>` | 손패 설정 후 즉시 분석. 예: `123456789m1299p5s` |
| `hand <패표기>` | 손패 설정 |
| `dora <패표기>` | 도라 표시패 설정 |
| `discard <패표기>` | 내 버림패 설정 (후리텐 판정용) |
| `meld <pon\|chi\|kan\|ankan> <패>` | 내 부로 추가 |
| `round <장풍> <자풍>` | 바람 설정 (E/S/W/N), 예: `round E S` |
| `turn <n>` | 순목 설정 |
| `tilesleft <n>` | 남은 산 매수 |
| `score <self> <s> <t> <k>` | 4자리 점수 |
| `myscore <n>` | 내 점수만 |

**패 표기**: `1m`-`9m` / `1p`-`9p` / `1s`-`9s` / `1z`-`7z`. 아카는 `0m`/`0p`/`0s`.
`z`: 1=동 2=남 3=서 4=북 5=백 6=발 7=중.

### 상대 정보

| 명령 | 설명 |
|---|---|
| `riichi <s\|t\|k>` | 그 자리(하가/대면/상가) 리치 표시 |
| `unriichi <s\|t\|k>` | 리치 해제 |
| `assume <s\|t\|k>` | 텐파이 의심 수동 추가 |
| `unassume <s\|t\|k>` | 텐파이 의심 해제 |
| `oppdiscard <s\|t\|k> <패>` | 그 자리 버림패 전체 (현물·스지·예측 판정용) |
| `oppmeld <s\|t\|k> <종류> <패>` | 그 자리 부로 추가 |

자리 별칭: `s`=하가(SHIMOCHA, 하가) / `t`=대면(TOIMEN) / `k`=상가(KAMICHA).

### 기타

| 명령 | 설명 |
|---|---|
| `show` | 현재 상태 출력 |
| `analyze` / `a` | 분석 재실행 |
| `clear` | 상태 초기화 |
| `help` / `?` | 도움말 |
| `quit` / `q` / `exit` | 종료 |

---

## 데모 (실측 출력)

### 텐파이 + 다마 vs 리치 비교 + 위험패 + 오시히키

입력:
```
turn 5
score 27000 32000 22000 19000
round S N
oppmeld s pon 666z
oppdiscard t 1m9p2z9s1p
234567m234567p5s
```

출력:
```
샹텐: 0 (텐파이)
[텐파이] 대기: 5s×3  (총 3매)
→ 리치 가능
타점(다마): 1판 40부 = 1300점
타점(리치): 2판 40부 = 2600점

[리치 판단] 리치 (リーチ)  (점수 +30)
   · 대기 보통 3매 (+5)
   · 다마텐 1300점 — 리치로 점프 큼 (+10)
   · 이른 순목 5 (+15)

[상대 역 예측]
  하가(s): 역패(6z)(확정)
  대면(t): 탕야오(가능)
      · 야오추 정리 5/5

[점수상황] 2등 27000점 — 모드: 1등 추격
   · 위와 5000점 차
   · 올라스 2등 — 5000점 차 추격, 만관 이상 필요

[역 추천]
 · 탕야오 (확정) — 야오추패 없음 — 그대로 진행
 · 핑후 (경향) — 커쯔 없는 순쯔 손
```

### 베타오리 시나리오 (다샹텐 + 2 리치)

```
> riichi s
> riichi t
> 2468m1357p2468s1z

[오시히키] 접기 (ベタオリ)  (점수 -80)
   · 4샹텐 — 화료 멀음 (−30)
   · 리치 상대 2명 (−50)
[베타오리 추천 순서] 2m → 8m → 1p → 2s → 8s → 1z
```

---

## 제공 분석 기능

| 기능 | 모듈 |
|---|---|
| **샹텐 / 우케이레 / 타패 추천** | `src/analysis/{shanten,efficiency}.py` |
| **후리텐 경고 / 役なし 경고** | `src/analysis/tenpai.py` |
| **타점 추정** (도라·아카·우라·리치 반영) | `src/analysis/value.py` |
| **역 추천** (탕야오·역패·혼/청일색·치또이·또이또이·핑후) | `src/analysis/yaku_suggest.py` |
| **위험패 분석** (현물·중/편스지·노찬스·원찬스·字牌·도라위험) | `src/analysis/danger.py` |
| **오시히키 판단** (밀기/접기 + 베타오리 순서) | `src/analysis/push_fold.py` |
| **리치 판단** (리치/다마/비추천) | `src/analysis/riichi_decide.py` |
| **부로 판단** (콜/스킵) | `src/analysis/call_decide.py` |
| **상대 역 예측** (버림패·부로 패턴) | `src/analysis/opp_yaku.py` |
| **점수상황·착순 전략** (올라스 모드) | `src/analysis/standings.py` |

전부 GameState 하나만 입력으로 받는 순수 함수 — 인식 레이어와 독립.

---

## 디렉토리 구조

```
ssuan_kor/
├─ main.py                  # 진입점 (--manual / --overlay / --phase0)
├─ requirements.txt
├─ PLAN.md                  # 설계·로드맵·진행 현황
├─ README.md
├─ AGENTS.md                # 모듈 구조 / 의존 관계 / 설계 노트
├─ src/
│  ├─ capture/              # 작혼 윈도우 탐색 + 화면 캡처 (dxcam/mss)
│  ├─ recognition/          # (Phase 1 인식부 — 미구현)
│  ├─ analysis/             # 분석 엔진 — OS 무관
│  ├─ core/                 # GameState 모델
│  ├─ cli/                  # 수동 입력 CLI (인식 없이 분석 즉시 사용)
│  └─ overlay/              # PyQt6 오버레이 UI
├─ assets/                  # (Phase 1 인식부 — 패 템플릿)
├─ models/                  # (Phase 4 — ONNX 모델)
└─ tests/                   # pytest (62 테스트, 분석 엔진 전체 커버)
```

---

## 개발

```bash
# 테스트 실행
python -m pytest tests/ -v

# 특정 모듈만
python -m pytest tests/test_phase3.py -v
```

분석 엔진은 Linux/macOS에서도 전부 동작·검증 가능. 캡처·오버레이는 Windows 권장
(오버레이는 Linux X11에서도 뜨지만 클릭 통과 미지원).

---

## 패 인식 (선택) — 인게임 캡처에서 자동 인식

**중요**: 인식엔 **인게임 환경 템플릿** 필요. reference sheet (도감) 템플릿은
환경 차이로 게임 화면과 매칭 안 됨.

### 절차
1. 작혼 1920x1080 창 모드, **친선전 vs AI** 또는 **리플레이** 모드
2. 손패 13~14장 보이는 시점 PNG 캡처 (다운스케일 X)
3. 한 캡처에서 정답을 알고 있는 손패로 템플릿 추출:
   ```bash
   python tools/collect_templates.py <capture.png> <theme_name>
   ```
   슬롯별 라벨 입력 (예: `2m`, `0p`, `5z`) → `assets/templates/<theme_name>/` 저장
4. 다른 캡처 인식 (CLI 안에서):
   ```
   > recognize path/to/screenshot.png mytheme
   ```
   인식된 손패로 자동 분석 진행.

### 한계
- 같은 해상도·같은 스킨이면 정확. **다른 해상도**(예: 1280x720 추출 → 955x537 적용)
  는 멀티스케일 매칭에도 한계.
- 좌표가 어긋나면 `tools/preview_profile.py <image>`로 시각 확인 후
  `config/profiles/default_16x9.yaml` 의 `my_hand` 값 미세조정.

### 도구
| 도구 | 역할 |
|---|---|
| `tools/preview_profile.py` | 프로파일 좌표를 이미지 위에 시각화 (캘리브레이션) |
| `tools/collect_templates.py` | 인게임 캡처서 슬롯 라벨링 → 테마 템플릿 추출 |
| `tools/extract_grid.py` | 도감 grid 시트에서 자동 추출 (참고용 — 인식 정확도엔 부적합) |

---

## Windows .exe 빌드 (선택)

Windows 사용자에게 단일 실행파일 배포:

```bash
pip install pyinstaller
python tools/build_exe.py --onefile
```

산출물: `dist/ssuan_kor.exe` — Python 설치 없이도 동작.
PyInstaller는 빌드 OS의 바이너리만 만든다 → Windows .exe는 Windows에서 빌드.

설정: [`ssuan_kor.spec`](ssuan_kor.spec) — datas, hiddenimports, excludes 조정 가능.

---

## 현황

- ✅ Phase 0: 캡처 PoC 코드 완료 (Windows 검증 대기)
- ✅ Phase 1 분석부: 샹텐 / 타패 추천 / 후리텐 / 役なし / 타점 / 역 추천
- ✅ Phase 2 분석부: 위험패 / 베타오리
- ✅ Phase 3 분석부: 오시히키 / 리치 판단 / 부로 판단 / 상대 역 예측 / 점수상황
- ✅ 수동 입력 CLI (모든 분석 즉시 사용 가능)
- ✅ 오버레이 셸 (PyQt6 frameless / translucent / 클릭 통과)
- ✅ 인식 PoC: 비율 좌표 프로파일 + 멀티스케일 템플릿 매칭 + 테마 시스템 + 추출 도구
- ✅ 작혼 창 자동 추적 + 실시간 캡처 루프 + 라이브 인식 (`--overlay --live`)
- ✅ PyInstaller spec + 빌드 스크립트 (Windows .exe)

---

## 주의

개인 학습용. 작혼 이용약관상 외부 도구는 회색지대 — 입력 자동화는 포함하지
않으며(읽기 전용 화면 캡처), 공개 배포 전 약관 재검토 필요.
