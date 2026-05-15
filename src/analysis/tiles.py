"""패 변환·계수 헬퍼.

Tile 리스트 ↔ mahjong 라이브러리용 34-array / 136-array 변환,
그리고 "보이는 패" 계수(우케이레·위험패 분석의 기반).
"""

from __future__ import annotations

from collections.abc import Iterable

from src.core.game_state import GameState, Meld, Tile

# mahjong 라이브러리의 아카도라 136-index (각 5의 첫 번째 사본)
AKA_136 = {"m": 16, "p": 52, "s": 88}  # 5m=idx34 4, 5p=13, 5s=22 → *4


def parse_hand(text: str) -> tuple[Tile, ...]:
    """\"123m456p11z\" 같은 표기를 Tile 튜플로.

    아카도라는 0 사용: \"0m\" = 빨강 5m.
    """
    tiles: list[Tile] = []
    digits: list[str] = []
    for ch in text:
        if ch.isdigit():
            digits.append(ch)
        elif ch in ("m", "p", "s", "z"):
            for d in digits:
                tiles.append(Tile.parse(d + ch))
            digits = []
        else:
            raise ValueError(f"패 표기에 잘못된 문자: {ch!r}")
    if digits:
        raise ValueError(f"suit 없는 숫자가 남음: {''.join(digits)}")
    return tuple(tiles)


def tiles_to_34(tiles: Iterable[Tile]) -> list[int]:
    """Tile들을 길이 34의 카운트 배열로."""
    arr = [0] * 34
    for t in tiles:
        arr[t.index34] += 1
    return arr


def meld_tiles(melds: Iterable[Meld]) -> list[Tile]:
    """부로들의 구성 패를 한 리스트로 펼침."""
    out: list[Tile] = []
    for m in melds:
        out.extend(m.tiles)
    return out


def hand_with_melds_34(
    hand: Iterable[Tile], melds: Iterable[Meld] = ()
) -> list[int]:
    """손패 + 부로 패를 합친 34-array.

    부로 패를 배열에 그대로 더하면 샹텐 계산 시 자연히 완성 면자로
    해석되므로, 별도 보정 없이 부로 포함 샹텐을 구할 수 있다.
    """
    return tiles_to_34(list(hand) + meld_tiles(melds))


def tiles_to_136(tiles: Iterable[Tile]) -> list[int]:
    """Tile들을 mahjong 라이브러리용 136-index 리스트로.

    아카 5는 해당 suit의 첫 사본 슬롯(16/52/88)에 배치하고,
    일반 패는 그 슬롯을 피해 채운다 (일반 5는 base+1~3만 사용 — 아카 슬롯 회피).
    """
    aka_slots = set(AKA_136.values())
    used: set[int] = set()
    result: list[int] = []
    # 아카 먼저 배치 (고정 슬롯)
    normals: list[Tile] = []
    for t in tiles:
        if t.is_aka:
            slot = AKA_136[t.suit]
            result.append(slot)
            used.add(slot)
        else:
            normals.append(t)
    # 일반 패 배치 — 아카 전용 슬롯은 피한다
    for t in normals:
        base = t.index34 * 4
        for offset in range(4):
            cand = base + offset
            if cand in used or cand in aka_slots:
                continue
            used.add(cand)
            result.append(cand)
            break
        else:
            raise ValueError(f"{t} 사본이 4장을 초과")
    return sorted(result)


def tile_to_136(tile: Tile) -> int:
    """단일 Tile → 대표 136-index (아카면 고정 슬롯)."""
    if tile.is_aka:
        return AKA_136[tile.suit]
    return tile.index34 * 4


def count_visible(state: GameState, index34: int) -> int:
    """해당 패가 화면상 몇 장 보이는지 — 내 손패·부로, 모든 버림패,
    모든 부로, 도라 표시패를 합산.
    """
    n = 0
    # 내 손패
    for t in state.my_hand:
        if t.index34 == index34:
            n += 1
    # 내 부로
    for t in meld_tiles(state.my_melds):
        if t.index34 == index34:
            n += 1
    # 내 버림패
    for d in state.my_discards:
        if d.tile.index34 == index34:
            n += 1
    # 상대 버림패
    for ds in state.discards.values():
        for d in ds:
            if d.tile.index34 == index34:
                n += 1
    # 상대 부로
    for ms in state.melds.values():
        for t in meld_tiles(ms):
            if t.index34 == index34:
                n += 1
    # 도라 표시패
    for t in state.dora_indicators:
        if t.index34 == index34:
            n += 1
    return n


def wall_remaining(state: GameState, index34: int) -> int:
    """해당 패가 아직 산·상대 손에 남아 있을 수 있는 최대 매수 (0~4)."""
    return max(0, 4 - count_visible(state, index34))
