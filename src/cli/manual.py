"""수동 입력 CLI — 패를 직접 입력해 분석 엔진을 즉시 사용.

인식 레이어(화면 캡처) 없이도 분석 엔진을 검증·활용할 수 있는 fallback.

실행:
    python main.py --manual

명령:
    <패표기>                  손패로 설정 후 바로 분석 (예: 123456789m1299p5s)
    hand <패표기>             손패 설정
    dora <패표기>             도라 표시패 설정
    discard <패표기>          내 버림패 설정 (후리텐 판정용)
    meld <종류> <패표기>      부로 추가 (종류: pon/chi/kan/ankan)
    round <장풍> <자풍>       바람 설정 (E/S/W/N), 예: round E S
    riichi <s|t|k>            그 자리(하가/대면/상가) 리치 표시
    unriichi <s|t|k>          리치 해제
    assume <s|t|k>            텐파이 의심 수동 추가 (리치 아닌 위협)
    unassume <s|t|k>          텐파이 의심 해제
    oppdiscard <s|t|k> <패>   그 자리의 버림패 전체 설정 (현물·스지 판정용)
    oppmeld <s|t|k> <종류> <패>  그 자리 부로 추가 (역패 폰 등 → 상대 역 예측)
    score <s> <s> <t> <k>     4자리 점수 동시 설정 (점수상황 판정)
    myscore <n>               내 점수만 설정 (리치 가능 판정)
    turn <n>                  순목 설정 (리치/오시히키 판단에 영향)
    tilesleft <n>             남은 산 매수 설정
    recognize <img> [theme]   이미지서 손패 인식 (인게임 캡처) → hand 자동 설정
    show                      현재 상태 출력
    analyze | a               분석 실행
    clear                     상태 초기화
    help | ?                  도움말
    quit | q                  종료
"""

from __future__ import annotations

import re

from src.core.game_state import (
    Discard,
    GameState,
    Meld,
    MeldType,
    RoundInfo,
    Seat,
    Tile,
    Wind,
)
from src.analysis.shanten import calculate_shanten
from src.analysis.efficiency import recommend_discards
from src.analysis.tenpai import tenpai_for_hand
from src.analysis.tiles import parse_hand
from src.analysis.value import best_value_among_waits
from src.analysis.yaku_suggest import suggest_yaku
from src.analysis.push_fold import Stance, evaluate_push_fold
from src.analysis.riichi_decide import RiichiAction, evaluate_riichi
from src.analysis.opp_yaku import predict_all_opponents
from src.analysis.standings import evaluate_standings

_TILE_NOTATION = re.compile(r"^[0-9]+[mpsz]([0-9]+[mpsz])*$")

_WIND_NAMES = {
    "E": Wind.EAST,
    "S": Wind.SOUTH,
    "W": Wind.WEST,
    "N": Wind.NORTH,
}
_WIND_LABEL = {
    Wind.EAST: "동(E)",
    Wind.SOUTH: "남(S)",
    Wind.WEST: "서(W)",
    Wind.NORTH: "북(N)",
}
_MELD_NAMES = {
    "pon": MeldType.PON,
    "chi": MeldType.CHI,
    "kan": MeldType.KAN,
    "ankan": MeldType.ANKAN,
}
# 상대 자리 별칭 → Seat
_SEAT_NAMES = {
    "s": Seat.SHIMOCHA,  # 하가
    "t": Seat.TOIMEN,    # 대면
    "k": Seat.KAMICHA,   # 상가
}
_SEAT_LABEL = {
    Seat.SHIMOCHA: "하가(s)",
    Seat.TOIMEN: "대면(t)",
    Seat.KAMICHA: "상가(k)",
}


class _StateBuilder:
    """CLI 세션 동안 누적되는 게임 상태."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.hand: tuple[Tile, ...] = ()
        self.melds: tuple[Meld, ...] = ()
        self.discards: tuple[Discard, ...] = ()
        self.dora: tuple[Tile, ...] = ()
        self.round_wind = Wind.EAST
        self.seat_wind = Wind.EAST
        # 상대 정보
        self.opp_discards: dict[Seat, tuple[Discard, ...]] = {}
        self.opp_melds: dict[Seat, tuple[Meld, ...]] = {}
        self.riichi_seats: set[Seat] = set()
        self.assume_tenpai: set[Seat] = set()
        # 게임 진행
        self.turn: int = 1
        self.tiles_left: int = 70
        self.scores: dict[Seat, int] = {}
        self.my_score: int = 25000

    def build(self) -> GameState:
        return GameState(
            my_hand=self.hand,
            my_melds=self.melds,
            my_discards=self.discards,
            discards=dict(self.opp_discards),
            melds=dict(self.opp_melds),
            riichi={s: True for s in self.riichi_seats},
            dora_indicators=self.dora,
            round=RoundInfo(round_wind=self.round_wind, seat_wind=self.seat_wind),
            scores=dict(self.scores),
            turn=self.turn,
            tiles_left=self.tiles_left,
        )


# --- 출력 포매팅 -----------------------------------------------------------

def _fmt_tiles(tiles: tuple[Tile, ...]) -> str:
    return "".join(str(t) for t in tiles) if tiles else "(없음)"


def format_state(b: _StateBuilder) -> str:
    lines = [
        f"  손패   : {_fmt_tiles(b.hand)}  ({len(b.hand)}장)",
        f"  부로   : "
        + (", ".join(f"{m.meld_type.value} {_fmt_tiles(m.tiles)}" for m in b.melds)
           if b.melds else "(없음)"),
        f"  내 버림패 : {_fmt_tiles(tuple(d.tile for d in b.discards))}",
        f"  도라표시: {_fmt_tiles(b.dora)}",
        f"  바람   : 장풍 {_WIND_LABEL[b.round_wind]} / 자풍 "
        f"{_WIND_LABEL[b.seat_wind]}",
    ]
    # 상대 자리별 정보
    for seat in (Seat.SHIMOCHA, Seat.TOIMEN, Seat.KAMICHA):
        ds = b.opp_discards.get(seat, ())
        flags = []
        if seat in b.riichi_seats:
            flags.append("리치")
        if seat in b.assume_tenpai:
            flags.append("텐파이의심")
        flag_str = f" [{', '.join(flags)}]" if flags else ""
        if ds or flags:
            lines.append(
                f"  {_SEAT_LABEL[seat]:8s}: 버림 {_fmt_tiles(tuple(d.tile for d in ds))}"
                f"{flag_str}"
            )
    return "\n".join(lines)


def format_analysis(
    state: GameState,
    assume_tenpai: frozenset[Seat] = frozenset(),
    my_score: int = 25000,
) -> str:
    hand = state.my_hand
    if not hand:
        return "[!] 손패가 비어 있음. 'hand <패표기>'로 입력하세요."

    n = len(hand)
    concealed_expected = 13 - 3 * len(state.my_melds)
    lines: list[str] = []

    sh = calculate_shanten(hand, state.my_melds)
    if sh.is_agari:
        lines.append("  ★ 완성형 (화료)")
    elif sh.is_tenpai:
        lines.append("  샹텐: 0 (텐파이)")
    else:
        lines.append(f"  샹텐: {sh.value}")
    lines.append(
        f"    (일반 {sh.regular} / 치또이 {sh.chiitoitsu} / 국사 {sh.kokushi})"
    )
    lines.append("")

    if n == concealed_expected + 1:
        # 쯔모 직후 — 타패 추천
        lines.append("  [타패 추천]  (좋은 순서)")
        opts = recommend_discards(state)
        for i, opt in enumerate(opts[:6], 1):
            uk = " ".join(f"{u.tile}×{u.count}" for u in opt.ukeire[:8])
            tail = " ..." if len(opt.ukeire) > 8 else ""
            mark = "←추천" if i == 1 else ""
            lines.append(
                f"   {i}. {opt.discard} 버림 → {opt.shanten}샹텐, "
                f"우케이레 {opt.ukeire_total}매 {opt.ukeire_types}종 {mark}"
            )
            if uk:
                lines.append(f"        {uk}{tail}")
    elif n == concealed_expected:
        # 대기 중 — 텐파이 분석
        info = tenpai_for_hand(
            hand,
            state.my_melds,
            state,
            state.round,
            frozenset(d.tile.index34 for d in state.my_discards),
        )
        if not info.is_tenpai:
            lines.append("  텐파이 아님 — 'hand'에 쯔모패 포함해 14장으로 입력하면"
                         " 타패 추천 가능")
        else:
            waits = " ".join(
                f"{w.tile}×{w.count}{'(役なし)' if w.is_yakuless else ''}"
                for w in info.waits
            )
            lines.append(f"  [텐파이] 대기: {waits}  (총 {info.waits_total}매)")
            if info.is_furiten:
                lines.append("  ⚠ 후리텐 — 론 불가 (쯔모만 가능)")
            if info.all_waits_yakuless:
                lines.append("  ⚠ 役なし 텐파이 — 론 불가 "
                             + ("(리치/쯔모만 가능)" if info.can_riichi
                                else "(부로 상태 — 화료 불가)"))
            if info.can_riichi and not info.is_furiten:
                lines.append("  → 리치 가능")

            # 타점 추정
            valid_waits = tuple(
                w.tile for w in info.waits if not w.is_yakuless
            )
            if valid_waits:
                v_dama = best_value_among_waits(
                    hand, valid_waits, state.my_melds,
                    state.dora_indicators, state.round,
                )
                if v_dama and v_dama.valid:
                    lines.append(f"  타점(다마): {v_dama.summary()}"
                                 + (f"  도라{v_dama.dora}" if v_dama.dora else ""))
            if info.can_riichi:
                v_ri = best_value_among_waits(
                    hand, tuple(w.tile for w in info.waits),
                    state.my_melds, state.dora_indicators, state.round,
                    is_riichi=True,
                )
                if v_ri and v_ri.valid:
                    lines.append(f"  타점(리치): {v_ri.summary()}"
                                 + (f"  도라{v_ri.dora}" if v_ri.dora else ""))
    else:
        lines.append(f"  [!] 손패 장수({n})가 분석 가능한 형태가 아님.")
        lines.append(f"      대기 중={concealed_expected}장, 쯔모 직후="
                     f"{concealed_expected + 1}장 이어야 함.")

    # 위험패 + 오시히키 — 위협이 있을 때만
    advice = evaluate_push_fold(state, assume_tenpai=assume_tenpai)
    if advice.danger_report.has_threat:
        lines.append("")
        lines.append(f"  [오시히키] {advice.stance.value}  (점수 {advice.score:+d})")
        for r in advice.reasons[:5]:
            lines.append(f"        · {r}")
        if advice.stance == Stance.FOLD and advice.safest_discard:
            order = advice.danger_report.safest_order
            preview = " → ".join(str(t) for t in order[:6])
            lines.append(f"  [베타오리 추천 순서] {preview}")

        lines.append("")
        lines.append("  [위험패] 손패 각 패 안전도 (낮을수록 안전)")
        for opp in advice.danger_report.per_opponent:
            seen: set[tuple] = set()
            tds = []
            for td in opp.tile_danger:
                key = (td.tile.suit, td.tile.rank)
                if key in seen:
                    continue
                seen.add(key)
                tds.append(td)
            tds.sort(key=lambda t: t.score)
            shown = " ".join(
                f"{td.tile}({td.score})" for td in tds[:10]
            )
            lines.append(f"    {_SEAT_LABEL[opp.seat]} ({opp.trigger}): {shown}")

    # 리치 판단 — 멘젠 + 텐파이일 때만 의미 있음
    if hand and len(hand) % 3 == 1:
        ri = evaluate_riichi(state, my_score=my_score)
        if ri.action != RiichiAction.NO_BET or any("멘젠" not in r for r in ri.reasons):
            lines.append("")
            lines.append(f"  [리치 판단] {ri.action.value}  (점수 {ri.score:+d})")
            for r in ri.reasons[:5]:
                lines.append(f"        · {r}")

    # 상대 역 예측 — 데이터 있는 자리만
    preds = predict_all_opponents(state)
    shown_preds = [
        p for p in preds
        if p.likely_yaku or state.discards.get(p.seat) or state.melds.get(p.seat)
    ]
    if shown_preds:
        lines.append("")
        lines.append("  [상대 역 예측]")
        for p in shown_preds:
            yaku_str = (
                ", ".join(f"{l.name}({l.status})" for l in p.likely_yaku[:4])
                or "특이 사항 없음"
            )
            lines.append(f"    {_SEAT_LABEL[p.seat]}: {yaku_str}")
            if p.discard_summary != "특이 패턴 없음":
                lines.append(f"        · {p.discard_summary}")

    # 점수상황 — 점수 입력된 경우만
    if state.scores:
        ctx = evaluate_standings(state)
        lines.append("")
        lines.append(f"  [점수상황] {ctx.my_rank}등 {ctx.my_score}점 — "
                     f"모드: {ctx.mode.value}")
        if ctx.gap_above is not None:
            lines.append(f"        · 위와 {ctx.gap_above}점 차")
        if ctx.gap_below is not None:
            lines.append(f"        · 아래와 {ctx.gap_below}점 차")
        lines.append(f"        · {ctx.note}")

    # 역 추천 — 항상 표시
    leads = suggest_yaku(state)
    if leads:
        lines.append("")
        lines.append("  [역 추천]")
        for lead in leads[:6]:
            lines.append(f"   · {lead.name} ({lead.status}) — {lead.note}")

    return "\n".join(lines)


# --- 명령 처리 -------------------------------------------------------------

_HELP = __doc__ or ""


def _cmd_meld(b: _StateBuilder, args: list[str]) -> str:
    if len(args) != 2 or args[0] not in _MELD_NAMES:
        return "사용법: meld <pon|chi|kan|ankan> <패표기>"
    mtype = _MELD_NAMES[args[0]]
    tiles = parse_hand(args[1])
    b.melds = b.melds + (Meld(meld_type=mtype, tiles=tiles),)
    return f"부로 추가: {args[0]} {args[1]}"


def _cmd_round(b: _StateBuilder, args: list[str]) -> str:
    if len(args) != 2 or args[0].upper() not in _WIND_NAMES \
            or args[1].upper() not in _WIND_NAMES:
        return "사용법: round <장풍 E/S/W/N> <자풍 E/S/W/N>"
    b.round_wind = _WIND_NAMES[args[0].upper()]
    b.seat_wind = _WIND_NAMES[args[1].upper()]
    return f"바람 설정: 장풍 {args[0].upper()} / 자풍 {args[1].upper()}"


def _resolve_seat(name: str) -> Seat | None:
    return _SEAT_NAMES.get(name.lower())


def _cmd_riichi(b: _StateBuilder, args: list[str], add: bool) -> str:
    if not args:
        return "사용법: riichi <s|t|k> (하가/대면/상가)"
    seat = _resolve_seat(args[0])
    if seat is None:
        return f"[!] 알 수 없는 자리: {args[0]}  (s/t/k 사용)"
    if add:
        b.riichi_seats.add(seat)
        return f"리치 표시: {_SEAT_LABEL[seat]}"
    b.riichi_seats.discard(seat)
    return f"리치 해제: {_SEAT_LABEL[seat]}"


def _cmd_assume(b: _StateBuilder, args: list[str], add: bool) -> str:
    if not args:
        return "사용법: assume <s|t|k>"
    seat = _resolve_seat(args[0])
    if seat is None:
        return f"[!] 알 수 없는 자리: {args[0]}"
    if add:
        b.assume_tenpai.add(seat)
        return f"텐파이 의심 표시: {_SEAT_LABEL[seat]}"
    b.assume_tenpai.discard(seat)
    return f"텐파이 의심 해제: {_SEAT_LABEL[seat]}"


def _cmd_oppdiscard(b: _StateBuilder, args: list[str]) -> str:
    if len(args) != 2:
        return "사용법: oppdiscard <s|t|k> <패표기>  (그 자리의 버림패 전체)"
    seat = _resolve_seat(args[0])
    if seat is None:
        return f"[!] 알 수 없는 자리: {args[0]}"
    tiles = parse_hand(args[1])
    b.opp_discards[seat] = tuple(
        Discard(tile=t, turn=i + 1) for i, t in enumerate(tiles)
    )
    return f"{_SEAT_LABEL[seat]} 버림패 설정: {_fmt_tiles(tiles)}"


def _cmd_recognize(b: _StateBuilder, args: list[str]) -> str:
    """recognize <image> [theme] — 이미지서 손패 인식 → builder.hand 설정."""
    if not args:
        return ("사용법: recognize <image_path> [theme]\n"
                "    image: 작혼 캡처 이미지 (PNG/JPG)\n"
                "    theme: assets/templates/ 아래 디렉토리 이름 (없으면 사용 가능 목록)")
    from pathlib import Path
    import cv2

    from src.recognition import (
        list_themes, load_profile, load_theme, recognize_my_hand,
    )

    img_path = Path(args[0])
    if not img_path.exists():
        return f"[!] 이미지 없음: {img_path}"
    theme_name = args[1] if len(args) > 1 else None
    if theme_name is None:
        themes = list_themes()
        return ("[!] 테마 미지정. 사용 가능: "
                + (", ".join(themes) if themes else "(없음 — tools/extract_grid.py 또는 collect_templates.py 실행)"))

    img = cv2.imread(str(img_path))
    if img is None:
        return f"[!] 이미지 로드 실패: {img_path}"
    profile_path = Path("config/profiles/default_16x9.yaml")
    if not profile_path.exists():
        return f"[!] 기본 프로파일 없음: {profile_path}"
    profile = load_profile(profile_path)
    try:
        theme = load_theme(theme_name)
    except FileNotFoundError as e:
        return f"[!] {e}"

    tiles, confs = recognize_my_hand(img, profile, theme, min_confidence=0.3)
    valid = tuple(t for t in tiles if t is not None)
    b.hand = valid
    avg_conf = sum(confs) / len(confs) if confs else 0.0
    low = sum(1 for c in confs if c < 0.5)
    lines = [
        f"인식 완료: {len(valid)}/{len(tiles)} 슬롯  (테마={theme_name}, 평균 신뢰도 {avg_conf:.2f})",
        "  " + " ".join(f"{str(t) if t else '?':>3}({c:.2f})"
                          for t, c in zip(tiles, confs)),
    ]
    if low:
        lines.append(f"  ⚠ {low}개 슬롯 신뢰도 < 0.5 — 직접 확인 필요. 'hand <패>' 로 보정")
    return "\n".join(lines)


def _cmd_oppmeld(b: _StateBuilder, args: list[str]) -> str:
    if len(args) != 3 or args[1] not in _MELD_NAMES:
        return "사용법: oppmeld <s|t|k> <pon|chi|kan|ankan> <패표기>"
    seat = _resolve_seat(args[0])
    if seat is None:
        return f"[!] 알 수 없는 자리: {args[0]}"
    mtype = _MELD_NAMES[args[1]]
    tiles = parse_hand(args[2])
    cur = b.opp_melds.get(seat, ())
    b.opp_melds[seat] = cur + (Meld(meld_type=mtype, tiles=tiles),)
    return f"{_SEAT_LABEL[seat]} 부로 추가: {args[1]} {args[2]}"


def _cmd_score(b: _StateBuilder, args: list[str]) -> str:
    """score <self> <shimo> <toi> <kami> — 4자리 점수 동시 설정."""
    if len(args) != 4:
        return "사용법: score <self> <shimo> <toi> <kami>  (예: score 25000 25000 25000 25000)"
    try:
        self_s, sh, ti, ka = (int(x) for x in args)
    except ValueError:
        return "[!] 점수는 정수여야 함"
    b.my_score = self_s
    b.scores = {
        Seat.SELF: self_s,
        Seat.SHIMOCHA: sh,
        Seat.TOIMEN: ti,
        Seat.KAMICHA: ka,
    }
    return f"점수 설정: SELF={self_s} S={sh} T={ti} K={ka}"


def _cmd_turn(b: _StateBuilder, args: list[str]) -> str:
    if not args:
        return "사용법: turn <순목>"
    try:
        b.turn = int(args[0])
    except ValueError:
        return "[!] 순목은 정수여야 함"
    return f"순목 설정: {b.turn}"


def _cmd_tilesleft(b: _StateBuilder, args: list[str]) -> str:
    if not args:
        return "사용법: tilesleft <남은 산 매수>"
    try:
        b.tiles_left = int(args[0])
    except ValueError:
        return "[!] 정수여야 함"
    return f"남은 산: {b.tiles_left}장"


def _cmd_myscore(b: _StateBuilder, args: list[str]) -> str:
    if not args:
        return "사용법: myscore <내 점수>"
    try:
        b.my_score = int(args[0])
        b.scores[Seat.SELF] = b.my_score
    except ValueError:
        return "[!] 정수여야 함"
    return f"내 점수: {b.my_score}"


def handle_command(b: _StateBuilder, line: str) -> tuple[str, bool]:
    """명령 한 줄 처리. 반환: (출력 메시지, 종료 여부)."""
    line = line.strip()
    if not line:
        return "", False

    # 패 표기만 입력 → 손패 설정 후 즉시 분석
    if _TILE_NOTATION.match(line):
        try:
            b.hand = parse_hand(line)
        except ValueError as e:
            return f"[!] {e}", False
        return format_analysis(b.build(), frozenset(b.assume_tenpai), b.my_score), False

    parts = line.split()
    cmd, args = parts[0].lower(), parts[1:]

    try:
        if cmd in ("quit", "q", "exit"):
            return "종료.", True
        if cmd in ("help", "h", "?"):
            return _HELP, False
        if cmd == "clear":
            b.reset()
            return "상태 초기화됨.", False
        if cmd == "show":
            return format_state(b), False
        if cmd in ("analyze", "a"):
            return format_analysis(b.build(), frozenset(b.assume_tenpai), b.my_score), False
        if cmd == "hand":
            b.hand = parse_hand(args[0]) if args else ()
            return f"손패 설정: {_fmt_tiles(b.hand)} ({len(b.hand)}장)", False
        if cmd == "dora":
            b.dora = parse_hand(args[0]) if args else ()
            return f"도라 표시패: {_fmt_tiles(b.dora)}", False
        if cmd == "discard":
            tiles = parse_hand(args[0]) if args else ()
            b.discards = tuple(
                Discard(tile=t, turn=i + 1) for i, t in enumerate(tiles)
            )
            return f"버림패 설정: {_fmt_tiles(tiles)}", False
        if cmd == "meld":
            return _cmd_meld(b, args), False
        if cmd == "round":
            return _cmd_round(b, args), False
        if cmd == "riichi":
            return _cmd_riichi(b, args, add=True), False
        if cmd == "unriichi":
            return _cmd_riichi(b, args, add=False), False
        if cmd == "assume":
            return _cmd_assume(b, args, add=True), False
        if cmd == "unassume":
            return _cmd_assume(b, args, add=False), False
        if cmd == "oppdiscard":
            return _cmd_oppdiscard(b, args), False
        if cmd == "oppmeld":
            return _cmd_oppmeld(b, args), False
        if cmd == "score":
            return _cmd_score(b, args), False
        if cmd == "myscore":
            return _cmd_myscore(b, args), False
        if cmd == "turn":
            return _cmd_turn(b, args), False
        if cmd == "tilesleft":
            return _cmd_tilesleft(b, args), False
        if cmd == "recognize":
            return _cmd_recognize(b, args), False
    except (ValueError, IndexError) as e:
        return f"[!] 입력 오류: {e}", False

    return f"[!] 알 수 없는 명령: {cmd}  ('help' 참고)", False


def run_manual_cli() -> int:
    """수동 입력 REPL 실행."""
    print("=" * 60)
    print(" 작혼 마작 어시스턴트 — 수동 입력 모드")
    print(" 패 표기를 바로 입력하면 분석합니다. 'help'로 도움말, 'q'로 종료.")
    print(" 예: 123456789m1299p5s")
    print("=" * 60)
    builder = _StateBuilder()
    while True:
        try:
            line = input("\n> ")
        except (EOFError, KeyboardInterrupt):
            print("\n종료.")
            return 0
        msg, should_quit = handle_command(builder, line)
        if msg:
            print(msg)
        if should_quit:
            return 0
