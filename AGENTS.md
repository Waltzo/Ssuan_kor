# AGENTS.md — 모듈 구조 / 설계 노트

향후 유지보수·확장을 위한 아키텍처 가이드.

## 1. 의존 그래프

```
                    ┌────────────────┐
                    │    main.py     │
                    └────┬───────┬───┘
            ┌────────────┘       └─────────────┐
            ▼                                  ▼
    ┌─────────────┐                   ┌─────────────┐
    │  src/cli    │                   │ src/overlay │
    │  (manual)   │◀──────────────────│  (window)   │
    └──────┬──────┘     handle_command└─────────────┘
           │ 재사용
           ▼
    ┌──────────────────────────────────────────────┐
    │              src/analysis/                   │
    │  (모든 분석 — OS 무관, GameState만 입력)     │
    └──────────┬───────────────────────────────────┘
               │
               ▼
    ┌──────────────────────────────────────────────┐
    │   src/core/game_state.py                     │
    │   (Tile, Meld, Discard, GameState 모델)      │
    └──────────────────────────────────────────────┘

    ┌─────────────┐
    │ src/capture │   (Windows 한정 — 작혼 창 탐색·캡처)
    └─────────────┘
    ┌─────────────────┐
    │ src/recognition │   (미구현 — 작혼 스크린샷 필요)
    └─────────────────┘
```

핵심 원칙: **분석 레이어는 캡처·UI에 의존하지 않는다**. GameState 하나만 입력으로
받아 결과를 반환. → Linux서 단위 테스트로 100% 검증 가능, 인식 레이어 작업과
병렬 진행 가능.

## 2. 분석 모듈 의존 관계

```
tiles.py        (변환·계수 — 의존 없음)
   ↓
shanten.py      (mahjong lib 래핑)
   ↓
efficiency.py   (우케이레·타패 추천)
   ↓
tenpai.py       (대기·후리텐·役なし) ──┐
                                      ├──┐
yaku_suggest.py (역 추천 휴리스틱) ────┤  │
                                      │  │
_libbridge.py   (mahjong lib 변환) ───┤  │
   ↓                                  │  │
value.py        (타점 추정) ──────────┤  │
                                      │  │
danger.py       (위험패 분석) ────────┤  │
   ↓                                  │  │
push_fold.py    (오시히키)◀───────────┘  │
                                          │
riichi_decide.py (리치 판단) ◀────────────┘
call_decide.py   (부로 판단) ← yaku_suggest, shanten
opp_yaku.py      (상대 역 예측) ← yaku_suggest
standings.py     (점수상황) ← game_state만
```

`_libbridge.py`는 mahjong 라이브러리 변환을 한 곳에 모은다 — 라이브러리 교체나
업그레이드 영향을 최소화.

## 3. GameState 모델 (`src/core/game_state.py`)

```python
@dataclass(frozen=True)
class GameState:
    my_hand: tuple[Tile, ...]
    my_melds: tuple[Meld, ...]
    my_discards: tuple[Discard, ...]
    discards: dict[Seat, tuple[Discard, ...]]   # 4인 (SELF 제외 사용)
    melds: dict[Seat, tuple[Meld, ...]]
    dora_indicators: tuple[Tile, ...]
    round: RoundInfo
    scores: dict[Seat, int]
    riichi: dict[Seat, bool]
    turn: int
    tiles_left: int
```

- **불변(frozen)**: 새 상태는 새 GameState로 만든다 (캡처 루프 친화적)
- **34-index 규칙**: m1~9=0~8, p1~9=9~17, s1~9=18~26, z1~7=27~33
- **아카도라**: `Tile.is_aka` 플래그 (5m/5p/5s만 가능)

## 4. 라이브러리 통합 주의사항

### mahjong 라이브러리 (`mahjong>=2.0`)

- `Shanten().calculate_shanten(arr34, use_chiitoitsu, use_kokushi)` — 부로는 34-array에 합산
- `HandCalculator().estimate_hand_value(...)` — 화료 시 판/부/타점
- **아카 슬롯 함정**: 일반 5m/5p/5s를 136-index 16/52/88에 배치하면 라이브러리가
  아카로 오인 → `tiles_to_136`과 `hand_and_win_136`은 아카 슬롯 회피 필수.
  과거 이 버그로 만관 오인이 발생함 → `_libbridge.py`에 가드 코드 있음.

### PyQt6 (overlay)

- frameless + translucent + always-on-top: `Qt.WindowType.FramelessWindowHint |
  WindowStaysOnTopHint | Tool` + `WA_TranslucentBackground`
- Windows 클릭 통과: `WS_EX_LAYERED | WS_EX_TRANSPARENT` (ctypes로 직접 호출)
- Linux에서는 클릭 통과 미지원 (X11 한계)

## 5. 휴리스틱 가중치 (튜닝 포인트)

각 결정 모듈은 점수화 + 임계값으로 결론 내림. 실전 데이터로 튜닝 가능한 위치:

| 모듈 | 변수 | 위치 |
|---|---|---|
| 위험패 점수 | `_BASE_SCORE` | `danger.py:38` |
| 오시히키 임계 | `score >= 20 / <= -20` | `push_fold.py:115` |
| 리치 판단 임계 | `score >= 25 / >= -10` | `riichi_decide.py:128` |
| 부로 판단 임계 | `score >= 20` | `call_decide.py:130` |
| 점수상황 모드 | 올라스 임계값 | `standings.py:73` |

NAGA·Mortal 같은 데이터 학습 모델로 교체 시 이 휴리스틱 부분만 갈아 끼우면 됨.

## 6. 테스트 전략

- 각 모듈 = 한 테스트 파일 (`tests/test_*.py`)
- 분석 엔진 전부 OS 무관 → Linux CI에서 완전 검증
- 인식 레이어는 향후 fixture screenshot 기반 통합 테스트 추가 예정
- 현재 62 테스트 통과

## 7. 미완성 영역 (인식 레이어)

`src/recognition/`은 비어 있다. 작업 시 필요:

1. 작혼 스크린샷 수집 (다양한 해상도·국면)
2. 손패 영역 좌표 측정 → `config/profiles/<해상도>.yaml`
3. 34종 패 + 아카 3종 템플릿 추출 → `assets/templates/`
4. 인식 함수: `recognize_hand(image, profile) -> tuple[Tile, ...]`
5. 신뢰도 함께 반환 → GameState.confidence

인식 모듈이 GameState를 만들면 즉시 분석 엔진과 오버레이가 연결된다.

## 8. 코딩 규약

- `from __future__ import annotations` (전 파일) — postponed annotations
- 한국어 docstring + 인라인 주석 (사용자 언어 기준)
- 데이터클래스 우선 (immutable, type-safe)
- 라이브러리 의존은 `_libbridge.py`에 모은다
