"""게임 상태 모델 — Tile, Meld, Discard, GameState.

작혼 화면에서 인식한 게임 상태를 담는 불변(immutable) 스냅샷.
분석 엔진은 이 모델만 입력으로 받는다 (OS·캡처와 무관, 단위 테스트 가능).

34-index 규칙:
    m1~9 = 0~8,  p1~9 = 9~17,  s1~9 = 18~26,  z1~7 = 27~33
    z: 1=동 2=남 3=서 4=북 5=백 6=발 7=중
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

SUITS = ("m", "p", "s", "z")
_SUIT_BASE = {"m": 0, "p": 9, "s": 18, "z": 27}
_BASE_SUIT = {0: "m", 9: "p", 18: "s", 27: "z"}


class Seat(Enum):
    """자신 기준 상대 위치."""

    SELF = 0
    SHIMOCHA = 1  # 하가 — 내 다음 차례
    TOIMEN = 2    # 대면
    KAMICHA = 3   # 상가 — 내 이전 차례


class Wind(Enum):
    """장풍·자풍."""

    EAST = 1
    SOUTH = 2
    WEST = 3
    NORTH = 4


class MeldType(Enum):
    CHI = "chi"                  # 치
    PON = "pon"                  # 폰
    KAN = "kan"                  # 대명깡 (남의 패로 깡)
    ANKAN = "ankan"              # 안깡 (혼자 깡)
    SHOUMINKAN = "shouminkan"    # 가깡 (폰 → 깡)


@dataclass(frozen=True, order=True)
class Tile:
    """마작 패 한 장.

    suit: 'm'|'p'|'s'|'z',  rank: m/p/s는 1~9, z는 1~7,  is_aka: 빨강5 여부.
    """

    suit: str
    rank: int
    is_aka: bool = False

    def __post_init__(self) -> None:
        if self.suit not in SUITS:
            raise ValueError(f"잘못된 suit: {self.suit!r}")
        max_rank = 7 if self.suit == "z" else 9
        if not 1 <= self.rank <= max_rank:
            raise ValueError(f"잘못된 rank: {self.suit}{self.rank}")
        if self.is_aka and not (self.suit in ("m", "p", "s") and self.rank == 5):
            raise ValueError("아카도라는 5m/5p/5s만 가능")

    @property
    def index34(self) -> int:
        """34-index (0~33)."""
        return _SUIT_BASE[self.suit] + self.rank - 1

    @classmethod
    def from_index34(cls, idx: int, is_aka: bool = False) -> "Tile":
        if not 0 <= idx <= 33:
            raise ValueError(f"34-index 범위 초과: {idx}")
        if idx >= 27:
            return cls("z", idx - 27 + 1, is_aka)
        base = (idx // 9) * 9
        return cls(_BASE_SUIT[base], idx - base + 1, is_aka)

    @classmethod
    def parse(cls, text: str) -> "Tile":
        """"5m", "1z", "0p"(아카 5p) 형식 파싱."""
        text = text.strip()
        if len(text) != 2 or text[1] not in SUITS:
            raise ValueError(f"패 표기 오류: {text!r}")
        suit = text[1]
        if text[0] == "0":  # 아카도라 표기
            return cls(suit, 5, is_aka=True)
        return cls(suit, int(text[0]), is_aka=False)

    @property
    def is_honor(self) -> bool:
        return self.suit == "z"

    @property
    def is_terminal(self) -> bool:
        """1·9 (수패 끝패)."""
        return self.suit != "z" and self.rank in (1, 9)

    @property
    def is_terminal_or_honor(self) -> bool:
        """야오추패 (1·9·字)."""
        return self.is_honor or self.is_terminal

    def __str__(self) -> str:
        return f"{'0' if self.is_aka else self.rank}{self.suit}"


@dataclass(frozen=True)
class Meld:
    """부로(鳴き) 또는 안깡."""

    meld_type: MeldType
    tiles: tuple[Tile, ...]
    called_from: Seat | None = None  # 누구 패로 울었는지 (안깡은 None)

    @property
    def is_open(self) -> bool:
        """공개 부로 여부 (안깡은 멘젠 유지 → False)."""
        return self.meld_type != MeldType.ANKAN


@dataclass(frozen=True)
class Discard:
    """버림패 한 장."""

    tile: Tile
    turn: int                       # 몇 순목에 버렸는지
    is_tsumogiri: bool = False      # 쯔모기리 (뽑은 패 즉시 버림)
    is_riichi_declare: bool = False # 리치 선언패 (옆으로 눕힌 패)


@dataclass(frozen=True)
class RoundInfo:
    """국(局) 정보."""

    round_wind: Wind = Wind.EAST
    seat_wind: Wind = Wind.EAST     # 내 자풍
    honba: int = 0                  # 본장
    riichi_sticks: int = 0          # 공탁 리치봉 수

    @property
    def is_dealer(self) -> bool:
        """내가 親(오야)인지."""
        return self.seat_wind == Wind.EAST


@dataclass(frozen=True)
class GameState:
    """한 시점의 게임 상태 스냅샷 (불변).

    분석 엔진의 유일한 입력. dict 필드는 관례상 생성 후 변경하지 않는다.
    """

    my_hand: tuple[Tile, ...] = ()
    my_melds: tuple[Meld, ...] = ()
    my_discards: tuple[Discard, ...] = ()
    discards: dict[Seat, tuple[Discard, ...]] = field(default_factory=dict)
    melds: dict[Seat, tuple[Meld, ...]] = field(default_factory=dict)
    dora_indicators: tuple[Tile, ...] = ()
    round: RoundInfo = field(default_factory=RoundInfo)
    scores: dict[Seat, int] = field(default_factory=dict)
    riichi: dict[Seat, bool] = field(default_factory=dict)
    turn: int = 1
    tiles_left: int = 70

    @property
    def is_menzen(self) -> bool:
        """멘젠(門前) 여부 — 공개 부로가 없으면 True (안깡은 멘젠 유지)."""
        return all(not m.is_open for m in self.my_melds)

    @property
    def hand_tile_count(self) -> int:
        """손패 장수 (부로 제외). 13=대기중, 14=쯔모 직후."""
        return len(self.my_hand)

    def all_opponent_discards(self) -> list[Discard]:
        """모든 상대 버림패를 한 리스트로."""
        out: list[Discard] = []
        for seat, ds in self.discards.items():
            if seat != Seat.SELF:
                out.extend(ds)
        return out
