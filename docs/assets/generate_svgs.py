"""README 용 애니메이션 SVG 생성기 — python3 docs/assets/generate_svgs.py docs/assets

GitHub 는 <img> 로 넣은 SVG 의 CSS 애니메이션을 재생한다 (스크립트는 불가).
기본 상태 = 애니메이션 마지막 장면 → 움직임 줄이기 설정에서도 완성 화면이 보인다.
"""

from __future__ import annotations

import sys
from pathlib import Path

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)

FONT = "'Pretendard','Apple SD Gothic Neo','Malgun Gothic','Noto Sans KR',sans-serif"
BASE_CSS = f"""
text{{font-family:{FONT};}}
.fb{{transform-box:fill-box;transform-origin:center;}}
@media (prefers-reduced-motion: reduce){{*{{animation:none!important;}}}}
"""


def kf(name: str, frames: list[tuple[float, str]]) -> str:
    body = " ".join(f"{p:g}%{{{css}}}" for p, css in frames)
    return f"@keyframes {name}{{{body}}}"


def appear(name: str, t_in: float, t_out: float = 94, extra_from: str = "", extra_to: str = "") -> str:
    """t_in% 에 나타나서 t_out% 까지 유지, 끝에서 사라진다 (전체 반복 리셋)."""
    return kf(
        name,
        [
            (0, f"opacity:0;{extra_from}"),
            (t_in, f"opacity:0;{extra_from}"),
            (t_in + 3, f"opacity:1;{extra_to}"),
            (t_out, f"opacity:1;{extra_to}"),
            (min(t_out + 4, 100), f"opacity:0;{extra_to}"),
            (100, f"opacity:0;{extra_to}"),
        ],
    )


def window(name: str, t_in: float, t_out: float) -> str:
    """t_in%~t_out% 동안만 보인다."""
    return kf(
        name,
        [
            (0, "opacity:0"),
            (max(t_in - 0.01, 0), "opacity:0"),
            (t_in, "opacity:1"),
            (t_out, "opacity:1"),
            (t_out + 0.01, "opacity:0"),
            (100, "opacity:0"),
        ],
    )


def svg(w: int, h: int, css: str, body: str, title: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'role="img" aria-label="{title}">\n<title>{title}</title>\n'
        f"<style>{BASE_CSS}{css}</style>\n{body}\n</svg>\n"
    )


def card_bg(w: int, h: int) -> str:
    return (
        '<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#ecfdf5"/><stop offset="1" stop-color="#f0f9ff"/></linearGradient></defs>'
        f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="28" fill="url(#bg)" stroke="#d1fae5" stroke-width="2"/>'
    )


# 공통 상품 그림 (cx, cy 중심) --------------------------------------------------
def bottle(cx: float, cy: float, s: float = 1.0, label: bool = True) -> str:
    def r(x, y, w, h, rx, fill):
        return f'<rect x="{cx + x * s:g}" y="{cy + y * s:g}" width="{w * s:g}" height="{h * s:g}" rx="{rx * s:g}" fill="{fill}"/>'

    out = r(-8, -52, 16, 18, 3, "#fbbf24") + r(-20, -38, 40, 86, 11, "#f59e0b")
    if label:
        out += r(-16, -8, 32, 26, 4, "#fff7ed")
        out += f'<text x="{cx:g}" y="{cy + 9 * s:g}" font-size="{7 * s:g}" font-weight="800" fill="#b45309" text-anchor="middle">OLIVE</text>'
    return out


# =============================================================================
# 1) hero.svg — 링크 붙여넣기 → AI 분석 → 체크리스트
# =============================================================================
def hero() -> str:
    W, H = 960, 420
    rows = [
        ("올리브 오일", "트레이더조", "#f59e0b"),
        ("아사이 퓌레", "트레이더조", "#7c3aed"),
        ("땅콩버터 프레첼", "트레이더조", "#b45309"),
        ("만다린 오렌지 치킨", "트레이더조", "#ef4444"),
        ("체리 피스타치오 그래놀라", "트레이더조", "#10b981"),
    ]
    css = [
        # 영상 속 상품이 빠르게 바뀌는 느낌 (2.4초 주기, 별도 반복)
        kf("f1", [(0, "opacity:1"), (24.9, "opacity:1"), (25, "opacity:0"), (100, "opacity:0")]),
        kf("f2", [(0, "opacity:0"), (24.9, "opacity:0"), (25, "opacity:1"), (49.9, "opacity:1"), (50, "opacity:0"), (100, "opacity:0")]),
        kf("f3", [(0, "opacity:0"), (49.9, "opacity:0"), (50, "opacity:1"), (74.9, "opacity:1"), (75, "opacity:0"), (100, "opacity:0")]),
        kf("f4", [(0, "opacity:0"), (74.9, "opacity:0"), (75, "opacity:1"), (100, "opacity:1")]),
        ".p1{animation:f1 2.4s infinite}.p2{animation:f2 2.4s infinite;opacity:0}"
        ".p3{animation:f3 2.4s infinite;opacity:0}.p4{animation:f4 2.4s infinite;opacity:0}",
        kf("prog", [(0, "transform:scaleX(0)"), (100, "transform:scaleX(1)")]),
        ".prog{transform-box:fill-box;transform-origin:left center;animation:prog 2.4s linear infinite}",
        # 링크 알약: 왼쪽 폰 → 입력창 (기본 위치 = 입력창 안)
        kf(
            "pill",
            [
                (0, "opacity:0;transform:translate(-270px,95px)"),
                (3, "opacity:1;transform:translate(-270px,95px)"),
                (14, "opacity:1;transform:translate(0,0)"),
                (94, "opacity:1;transform:translate(0,0)"),
                (98, "opacity:0;transform:translate(0,0)"),
                (100, "opacity:0;transform:translate(-270px,95px)"),
            ],
        ),
        ".pill{animation:pill 10s ease-in-out infinite}",
        kf("ph", [(0, "opacity:1"), (12, "opacity:1"), (13, "opacity:0"), (98, "opacity:0"), (100, "opacity:1")]),
        ".ph{opacity:0;animation:ph 10s infinite}",
        kf("btn", [(0, "transform:scale(1)"), (16, "transform:scale(1)"), (18, "transform:scale(.92)"), (20, "transform:scale(1)"), (100, "transform:scale(1)")]),
        ".btn{animation:btn 10s infinite}",
        kf("spin", [(0, "transform:rotate(0)"), (100, "transform:rotate(360deg)")]),
        ".ring{animation:spin 3s linear infinite}",
        appear("ai", 18, 94),
        ".ai{animation:ai 10s infinite}",
        kf("scan", [(0, "transform:translateY(-18px)"), (50, "transform:translateY(18px)"), (100, "transform:translateY(-18px)")]),
        ".scan{animation:scan 1.6s ease-in-out infinite}",
        kf("dash", [(0, "stroke-dashoffset:24"), (100, "stroke-dashoffset:0")]),
        ".flow{animation:dash .8s linear infinite}",
    ]
    for i in range(len(rows)):
        t = 42 + i * 5
        css.append(appear(f"r{i}", t, 94, "transform:translateY(8px)", "transform:translateY(0)"))
        css.append(f".r{i}{{animation:r{i} 10s infinite}}")
    for name, t in (("c0", 72), ("c2", 80)):
        css.append(appear(name, t, 94))
        css.append(f".{name}{{animation:{name} 10s infinite}}")

    body = [card_bg(W, H)]
    # 왼쪽: SNS 영상 폰
    body.append(
        '<g transform="translate(70,40)">'
        '<rect width="190" height="320" rx="28" fill="#0f172a"/>'
        '<rect x="10" y="12" width="170" height="296" rx="20" fill="#1e293b"/>'
        '<text x="95" y="44" font-size="12" font-weight="800" fill="#fff" text-anchor="middle">트레이더조 추천템</text>'
        '<text x="95" y="62" font-size="12" font-weight="800" fill="#fde68a" text-anchor="middle">26가지 🛒</text>'
        f'<g class="p1">{bottle(95, 170)}</g>'
        '<g class="p2"><rect x="58" y="128" width="74" height="84" rx="8" fill="#ef4444"/><rect x="58" y="160" width="74" height="16" fill="#fff"/>'
        '<text x="95" y="172" font-size="9" font-weight="800" fill="#ef4444" text-anchor="middle">CHICKEN</text></g>'
        '<g class="p3"><rect x="64" y="122" width="62" height="16" rx="5" fill="#6d28d9"/><rect x="68" y="134" width="54" height="76" rx="14" fill="#8b5cf6"/>'
        '<text x="95" y="178" font-size="9" font-weight="800" fill="#fff" text-anchor="middle">ACAI</text></g>'
        '<g class="p4"><path d="M60 140 Q95 118 130 140 L124 214 Q95 222 66 214 Z" fill="#10b981"/>'
        '<text x="95" y="182" font-size="9" font-weight="800" fill="#fff" text-anchor="middle">GRANOLA</text></g>'
        '<rect x="24" y="270" width="142" height="4" rx="2" fill="#334155"/>'
        '<rect class="prog" x="24" y="270" width="142" height="4" rx="2" fill="#f43f5e"/>'
        '<text x="24" y="292" font-size="10" fill="#94a3b8">▶ 0:20</text>'
        "</g>"
        '<text x="165" y="392" font-size="15" font-weight="800" fill="#0f172a" text-anchor="middle">SNS 장보기 영상</text>'
    )
    # 가운데: 입력창 + AI
    body.append(
        '<rect x="320" y="70" width="320" height="50" rx="25" fill="#fff" stroke="#a7f3d0" stroke-width="2"/>'
        '<text class="ph" x="344" y="100" font-size="13" fill="#94a3b8">영상 링크를 붙여넣으세요</text>'
        '<g class="pill"><rect x="334" y="80" width="196" height="30" rx="15" fill="#d1fae5"/>'
        '<text x="350" y="100" font-size="12" font-weight="700" fill="#047857">🔗 instagram.com/reel/…</text></g>'
        '<g class="btn fb"><rect x="540" y="78" width="92" height="34" rx="17" fill="#059669"/>'
        '<text x="586" y="100" font-size="12.5" font-weight="800" fill="#fff" text-anchor="middle">리스트 만들기</text></g>'
        '<g class="ai">'
        '<circle cx="480" cy="225" r="54" fill="#fff" stroke="#d1fae5" stroke-width="2"/>'
        '<g class="ring fb"><circle cx="480" cy="225" r="46" fill="none" stroke="#10b981" stroke-width="4" stroke-dasharray="18 12" stroke-linecap="round"/></g>'
        '<rect x="458" y="207" width="44" height="36" rx="7" fill="#0f172a"/>'
        '<path d="M474 216 L490 225 L474 234 Z" fill="#fff"/>'
        '<g class="scan"><rect x="452" y="223" width="56" height="3" rx="1.5" fill="#34d399" opacity=".9"/></g>'
        '<text x="480" y="310" font-size="15" font-weight="800" fill="#0f172a" text-anchor="middle">AI가 영상을 끝까지 보고</text>'
        '<text x="480" y="332" font-size="13" fill="#475569" text-anchor="middle">상품 · 제품 사진 · 추천 이유를 찾아요</text>'
        "</g>"
        '<path class="flow" d="M545 225 H690" stroke="#10b981" stroke-width="3" stroke-dasharray="8 4" fill="none"/>'
        '<path d="M684 217 L694 225 L684 233" stroke="#10b981" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
        '<path class="flow" d="M270 200 Q300 150 330 125" stroke="#94a3b8" stroke-width="2" stroke-dasharray="6 6" fill="none"/>'
    )
    # 오른쪽: 체크리스트 폰
    r = ['<g transform="translate(700,40)">'
         '<rect width="190" height="320" rx="28" fill="#fff" stroke="#e2e8f0" stroke-width="2"/>'
         '<rect x="70" y="10" width="50" height="6" rx="3" fill="#e2e8f0"/>'
         '<text x="18" y="44" font-size="14" font-weight="800" fill="#0f172a">내 장보기 리스트</text>'
         '<text x="18" y="61" font-size="10.5" fill="#64748b">트레이더조 추천템 · 영상 1개</text>']
    for i, (name, shop, color) in enumerate(rows):
        y = 74 + i * 46
        r.append(
            f'<g class="r{i}"><rect x="10" y="{y}" width="170" height="40" rx="10" fill="#f8fafc"/>'
            f'<circle cx="26" cy="{y + 20}" r="9" fill="#059669"/>'
            f'<text x="26" y="{y + 24}" font-size="10" font-weight="800" fill="#fff" text-anchor="middle">{i + 1}</text>'
            f'<rect x="40" y="{y + 7}" width="26" height="26" rx="6" fill="{color}" opacity=".85"/>'
            f'<text x="73" y="{y + 18}" font-size="11" font-weight="800" fill="#0f172a">{name if len(name) < 10 else name[:9] + "…"}</text>'
            f'<text x="73" y="{y + 32}" font-size="9" fill="#64748b">{shop}</text>'
            f'<rect x="156" y="{y + 12}" width="16" height="16" rx="4" fill="#fff" stroke="#cbd5e1" stroke-width="1.5"/>'
        )
        if i in (0, 2):
            r.append(
                f'<g class="c{i}"><rect x="156" y="{y + 12}" width="16" height="16" rx="4" fill="#10b981"/>'
                f'<path d="M160 {y + 20} l3 3 l6 -6" stroke="#fff" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
                f'<line x1="73" y1="{y + 14}" x2="{73 + min(len(name), 9) * 10.5:g}" y2="{y + 14}" stroke="#94a3b8" stroke-width="1.5"/></g>'
            )
        r.append("</g>")
    r.append("</g>")
    body.append("".join(r))
    body.append('<text x="795" y="392" font-size="15" font-weight="800" fill="#0f172a" text-anchor="middle">체크리스트 완성 ✓</text>')
    return svg(W, H, "".join(css), "\n".join(body), "SNS 영상 링크를 붙여넣으면 AI가 장보기 체크리스트를 만들어요")


# =============================================================================
# 2) how-it-works.svg — 4단계
# =============================================================================
def how() -> str:
    W, H = 960, 270
    steps = [
        ("링크 붙여넣기", "인스타·유튜브·틱톡", "영상 링크를 복사해 넣어요"),
        ("AI가 영상 시청", "화면 자막과 말소리까지", "보고 상품을 찾아요"),
        ("제품 사진 고르기", "장면 5컷 중 제품이", "가장 잘 보이는 1컷"),
        ("체크리스트 완성", "번호·판매처별로 정리,", "장 보면서 체크!"),
    ]
    icons = [
        # 링크
        '<g transform="rotate(-35 0 0)" fill="none" stroke="#059669" stroke-width="4">'
        '<rect x="-20" y="-7" width="22" height="14" rx="7"/><rect x="-2" y="-7" width="22" height="14" rx="7"/></g>',
        # 재생 + 반짝
        '<rect x="-18" y="-13" width="32" height="26" rx="6" fill="#059669"/><path d="M-7 -6 L5 0 L-7 6 Z" fill="#fff"/>'
        '<path d="M16 -18 l2 5 l5 2 l-5 2 l-2 5 l-2 -5 l-5 -2 l5 -2 Z" fill="#f59e0b"/>',
        # 프레임 3장
        '<rect x="-24" y="-9" width="14" height="18" rx="3" fill="#a7f3d0"/><rect x="10" y="-9" width="14" height="18" rx="3" fill="#a7f3d0"/>'
        '<rect x="-9" y="-14" width="18" height="28" rx="4" fill="#fff" stroke="#059669" stroke-width="3"/>',
        # 체크리스트
        '<path d="M-18 -10 l3 3 l5 -5 M-18 3 l3 3 l5 -5" stroke="#059669" stroke-width="3" fill="none" stroke-linecap="round"/>'
        '<rect x="-3" y="-11" width="22" height="4" rx="2" fill="#059669"/><rect x="-3" y="2" width="18" height="4" rx="2" fill="#059669"/>'
        '<rect x="-18" y="14" width="37" height="4" rx="2" fill="#a7f3d0"/>',
    ]
    css = []
    for i in range(4):
        css.append(window(f"g{i}", i * 25, (i + 1) * 25))
        css.append(f".g{i}{{animation:g{i} 8s infinite}}")
        css.append(kf(f"b{i}", [(0, "transform:scale(1)"), (i * 25, "transform:scale(1)"), (i * 25 + 4, "transform:scale(1.15)"), (i * 25 + 9, "transform:scale(1)"), (100, "transform:scale(1)")]))
        css.append(f".b{i}{{animation:b{i} 8s infinite}}")
    css.append(kf("dot", [(0, "transform:translateX(0)")] + [(p, f"transform:translateX({x}px)") for p, x in ((25, 235), (50, 470), (75, 705), (100, 705))]))
    css.append(".dot{animation:dot 8s cubic-bezier(.6,0,.4,1) infinite}")

    body = [card_bg(W, H)]
    body.append('<line x1="135" y1="105" x2="840" y2="105" stroke="#d1fae5" stroke-width="4" stroke-linecap="round"/>')
    body.append('<g class="dot"><circle cx="135" cy="105" r="7" fill="#10b981"/></g>')
    for i, (title, d1, d2) in enumerate(steps):
        x = 35 + i * 235
        cx = x + 100
        body.append(
            f'<rect x="{x}" y="34" width="200" height="206" rx="20" fill="#fff" stroke="#e2e8f0" stroke-width="2"/>'
            f'<rect class="g{i}" x="{x}" y="34" width="200" height="206" rx="20" fill="none" stroke="#10b981" stroke-width="3"/>'
            f'<g class="b{i} fb"><circle cx="{cx}" cy="105" r="36" fill="#ecfdf5"/>'
            f'<g transform="translate({cx},105)">{icons[i]}</g></g>'
            f'<circle cx="{x + 26}" cy="60" r="13" fill="#059669"/>'
            f'<text x="{x + 26}" y="65" font-size="13" font-weight="800" fill="#fff" text-anchor="middle">{i + 1}</text>'
            f'<text x="{cx}" y="175" font-size="16" font-weight="800" fill="#0f172a" text-anchor="middle">{title}</text>'
            f'<text x="{cx}" y="200" font-size="12" fill="#64748b" text-anchor="middle">{d1}</text>'
            f'<text x="{cx}" y="218" font-size="12" fill="#64748b" text-anchor="middle">{d2}</text>'
        )
    return svg(W, H, "".join(css), "\n".join(body), "링크템 사용 4단계: 링크 붙여넣기, AI가 영상 시청, 제품 사진 고르기, 체크리스트 완성")


# =============================================================================
# 3) photo-pick.svg — 5컷 중 1컷 고르기
# =============================================================================
def photo() -> str:
    W, H = 960, 330
    labels = ["-1초", "-0.5초", "딱 그때", "+0.5초", "+1초"]
    verdicts = [("흔들림", "#ef4444"), ("잘림", "#ef4444"), ("손에 가림", "#ef4444"), ("선명 ✓", "#059669"), ("흔들림", "#ef4444")]
    css = [
        kf(
            "scanner",
            [(0, "opacity:0;transform:translateX(0)"), (4, "opacity:1;transform:translateX(0)")]
            + [(4 + 10 * k, f"opacity:1;transform:translateX({116 * k}px)") for k in range(5)]
            + [(55, "opacity:1;transform:translateX(348px)"), (94, "opacity:1;transform:translateX(348px)"), (98, "opacity:0;transform:translateX(348px)"), (100, "opacity:0;transform:translateX(0)")],
        ),
        ".scanner{transform:translateX(348px);animation:scanner 9s ease-in-out infinite}",
        appear("pick", 55, 94),
        ".pick{animation:pick 9s infinite}",
        appear("out1", 62, 94, "transform:translateX(-30px)", "transform:translateX(0)"),
        appear("out2", 70, 94, "transform:translateX(-30px)", "transform:translateX(0)"),
        ".out1{animation:out1 9s infinite}.out2{animation:out2 9s infinite}",
        kf("dash", [(0, "stroke-dashoffset:24"), (100, "stroke-dashoffset:0")]),
        ".flow{animation:dash .8s linear infinite}",
    ]
    for k in range(5):
        css.append(appear(f"v{k}", 6 + 10 * k, 94))
        css.append(f".v{k}{{animation:v{k} 9s infinite}}")

    body = [card_bg(W, H)]
    body.append(
        '<defs><filter id="blur" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="3.5"/></filter>'
        '<filter id="mblur" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="4 0.5"/></filter>'
    )
    for k in range(5):
        x = 52 + k * 116
        body.append(f'<clipPath id="cf{k}"><rect x="{x}" y="88" width="104" height="104" rx="6"/></clipPath>')
    body.append("</defs>")
    body.append('<text x="40" y="52" font-size="16" font-weight="800" fill="#0f172a">상품이 나온 순간 앞뒤로 5컷을 뽑고 →</text>')
    body.append('<text x="680" y="52" font-size="16" font-weight="800" fill="#0f172a">AI가 1컷을 골라요</text>')
    # 필름
    body.append('<rect x="36" y="70" width="600" height="140" rx="12" fill="#0f172a"/>')
    for j in range(15):
        hx = 48 + j * 40
        body.append(f'<rect x="{hx}" y="76" width="18" height="7" rx="2" fill="#334155"/><rect x="{hx}" y="197" width="18" height="7" rx="2" fill="#334155"/>')
    for k in range(5):
        x = 52 + k * 116
        cx, cy = x + 52, 148
        body.append(f'<rect x="{x}" y="88" width="104" height="104" rx="6" fill="#e2e8f0"/>')
        g = f'<g clip-path="url(#cf{k})">'
        if k == 0:
            g += f'<g filter="url(#blur)">{bottle(cx, cy, .82)}</g>'
        elif k == 1:
            g += bottle(cx + 44, cy + 6, .82)
        elif k == 2:
            g += bottle(cx, cy, .82) + f'<ellipse cx="{cx - 4}" cy="{cy + 6}" rx="34" ry="26" fill="#fdba74"/><rect x="{cx - 50}" y="{cy}" width="30" height="18" rx="9" fill="#fdba74"/>'
        elif k == 3:
            g += bottle(cx, cy, .82)
        else:
            g += f'<g filter="url(#mblur)" opacity=".7">{bottle(cx - 10, cy, .82)}</g><g filter="url(#mblur)" opacity=".7">{bottle(cx + 10, cy, .82)}</g>'
        g += "</g>"
        body.append(g)
        body.append(f'<text x="{cx}" y="234" font-size="12" font-weight="700" fill="#475569" text-anchor="middle">{labels[k]}</text>')
        vt, vc = verdicts[k]
        body.append(f'<text class="v{k}" x="{cx}" y="256" font-size="12" font-weight="800" fill="{vc}" text-anchor="middle">{vt}</text>')
    body.append('<g class="scanner"><rect x="47" y="83" width="114" height="114" rx="9" fill="none" stroke="#34d399" stroke-width="4"/></g>')
    body.append(
        '<g class="pick"><rect x="389" y="62" width="62" height="20" rx="10" fill="#059669"/>'
        '<text x="420" y="76" font-size="11" font-weight="800" fill="#fff" text-anchor="middle">AI 선택</text></g>'
    )
    body.append('<path class="flow" d="M640 140 H674" stroke="#10b981" stroke-width="3" stroke-dasharray="8 4" fill="none"/>')
    body.append(
        '<g class="out1"><rect x="680" y="72" width="128" height="148" rx="14" fill="#fff" stroke="#10b981" stroke-width="2"/>'
        '<rect x="692" y="84" width="104" height="104" rx="8" fill="#e2e8f0"/>' + bottle(744, 140, .9) +
        '<text x="744" y="208" font-size="12" font-weight="800" fill="#0f172a" text-anchor="middle">확대 보기용</text>'
        '<text x="744" y="246" font-size="11" fill="#64748b" text-anchor="middle">선명하게 · 50KB 이하</text></g>'
    )
    body.append(
        '<g class="out2"><rect x="826" y="112" width="96" height="108" rx="14" fill="#fff" stroke="#a7f3d0" stroke-width="2"/>'
        '<rect x="846" y="124" width="56" height="56" rx="6" fill="#e2e8f0"/>' + bottle(874, 154, .5, label=False) +
        '<text x="874" y="206" font-size="12" font-weight="800" fill="#0f172a" text-anchor="middle">목록용</text>'
        '<text x="874" y="246" font-size="11" fill="#64748b" text-anchor="middle">작고 빠르게</text></g>'
    )
    body.append('<text x="480" y="300" font-size="12.5" fill="#475569" text-anchor="middle">상품 이름과 가장 잘 맞고 선명한 컷을 골라요 · 사진이 틀렸다는 제보가 모이면 범위를 넓혀 다시 골라요</text>')
    return svg(W, H, "".join(css), "\n".join(body), "상품이 나온 순간 앞뒤 5컷 중 AI가 가장 선명한 1컷을 고르는 과정")


# =============================================================================
# 4) accuracy.svg — 여러 사람이 넣을수록 정확해진다
# =============================================================================
def accuracy() -> str:
    W, H = 960, 360
    people_t = [5, 20, 35, 50, 65]
    colors = ["#10b981", "#3b82f6", "#f59e0b", "#ec4899", "#8b5cf6"]
    rows = [
        ("올리브 오일", [1, 1, 1, 1, 1]),
        ("아사이 퓌레", [0, 1, 1, 1, 1]),
        ("모찌 아이스크림", [1, 0, 0, 0, 0]),
    ]
    lock_t = 78
    css = []
    for i, t in enumerate(people_t):
        css.append(appear(f"pp{i}", t, 94, "transform:scale(.4)", "transform:scale(1)"))
        css.append(f".pp{i}{{animation:pp{i} 10s infinite}}")
        nxt = people_t[i + 1] if i + 1 < len(people_t) else lock_t
        css.append(window(f"cn{i}", t, nxt))
        css.append(f".cn{i}{{opacity:0;animation:cn{i} 10s infinite}}")
    css.append(appear("lock", lock_t, 94, "transform:scale(.6)", "transform:scale(1)"))
    css.append(".lock{animation:lock 10s infinite}")
    css.append(appear("drop", people_t[2] + 2, 94))
    css.append(".drop{animation:drop 10s infinite}")
    css.append(kf("fade", [(0, "opacity:1"), (people_t[2] + 2, "opacity:1"), (people_t[2] + 5, "opacity:.35"), (96, "opacity:.35"), (100, "opacity:1")]))
    css.append(".fade{opacity:.35;animation:fade 10s infinite}")
    for r_i, (_, votes) in enumerate(rows):
        for i, v in enumerate(votes):
            css.append(appear(f"d{r_i}{i}", people_t[i] + 1, 94, "transform:scale(0)", "transform:scale(1)"))
            css.append(f".d{r_i}{i}{{animation:d{r_i}{i} 10s infinite}}")

    body = [card_bg(W, H)]
    body.append('<text x="40" y="50" font-size="16" font-weight="800" fill="#0f172a">다른 사람이 같은 영상을 넣을 때마다 AI가 한 번 더 확인해요</text>')
    for i, c in enumerate(colors):
        cx = 72 + i * 92
        body.append(
            f'<g class="pp{i} fb"><circle cx="{cx}" cy="100" r="26" fill="{c}" opacity=".15"/>'
            f'<circle cx="{cx}" cy="93" r="8" fill="{c}"/><path d="M{cx - 14} 116 Q{cx} 98 {cx + 14} 116 Z" fill="{c}"/>'
            f'<text x="{cx}" y="145" font-size="11.5" font-weight="700" fill="#475569" text-anchor="middle">{i + 1}번째 분석</text></g>'
        )
    # 검증 배지
    for i in range(5):
        body.append(
            f'<g class="cn{i}"><rect x="660" y="78" width="250" height="44" rx="22" fill="#ede9fe"/>'
            f'<text x="785" y="106" font-size="15" font-weight="800" fill="#6d28d9" text-anchor="middle">✨ AI 검증 {i + 1}/5</text></g>'
        )
    body.append(
        '<g class="lock fb"><rect x="660" y="78" width="250" height="44" rx="22" fill="#d1fae5"/>'
        '<text x="785" y="106" font-size="15" font-weight="800" fill="#047857" text-anchor="middle">🔒 AI 검증 완료 · 결과 확정</text></g>'
    )
    # 상품 표
    body.append('<rect x="36" y="168" width="888" height="166" rx="18" fill="#fff" stroke="#e2e8f0" stroke-width="2"/>')
    body.append('<text x="64" y="196" font-size="11.5" font-weight="700" fill="#94a3b8">AI가 찾은 상품</text>')
    body.append('<text x="430" y="196" font-size="11.5" font-weight="700" fill="#94a3b8">회차별로 찾았나?</text>')
    body.append('<text x="700" y="196" font-size="11.5" font-weight="700" fill="#94a3b8">결과</text>')
    for r_i, (name, votes) in enumerate(rows):
        y = 230 + r_i * 38
        is_drop = r_i == 2
        row = [f'<g class="{"fade" if is_drop else ""}">', f'<text x="64" y="{y + 5}" font-size="14" font-weight="800" fill="#0f172a">{name}</text>']
        for i, v in enumerate(votes):
            dx = 440 + i * 40
            row.append(f'<circle cx="{dx}" cy="{y}" r="11" fill="none" stroke="#e2e8f0" stroke-width="2"/>')
            if v:
                row.append(f'<g class="d{r_i}{i} fb"><circle cx="{dx}" cy="{y}" r="11" fill="{colors[i]}"/>'
                           f'<path d="M{dx - 5} {y} l3.5 3.5 l6.5 -6.5" stroke="#fff" stroke-width="2.2" fill="none" stroke-linecap="round"/></g>')
            else:
                row.append(f'<g class="d{r_i}{i} fb"><path d="M{dx - 4} {y - 4} l8 8 M{dx + 4} {y - 4} l-8 8" stroke="#cbd5e1" stroke-width="2.2" stroke-linecap="round"/></g>')
        row.append("</g>")
        body.append("".join(row))
        if is_drop:
            body.append(
                f'<g class="drop"><line x1="60" y1="{y}" x2="196" y2="{y}" stroke="#ef4444" stroke-width="2"/>'
                f'<rect x="700" y="{y - 13}" width="196" height="26" rx="13" fill="#fee2e2"/>'
                f'<text x="798" y="{y + 5}" font-size="12" font-weight="800" fill="#b91c1c" text-anchor="middle">절반 넘게 못 찾음 → 제외</text></g>'
            )
        else:
            body.append(
                f'<rect x="700" y="{y - 13}" width="120" height="26" rx="13" fill="#d1fae5"/>'
                f'<text x="760" y="{y + 5}" font-size="12" font-weight="800" fill="#047857" text-anchor="middle">리스트에 남김</text>'
            )
    return svg(W, H, "".join(css), "\n".join(body), "여러 사람이 같은 영상을 넣으면 AI가 최대 5번 교차 확인해 결과를 확정하는 과정")


for name, fn in (("hero", hero), ("how-it-works", how), ("photo-pick", photo), ("accuracy", accuracy)):
    (OUT / f"{name}.svg").write_text(fn(), encoding="utf-8")
    print("wrote", name)
