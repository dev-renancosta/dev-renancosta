#!/usr/bin/env python3
"""Gera as imagens animadas do README do perfil.

- assets/header.svg: o porto de Itajaí no horário e clima reais. Os prédios
  ao fundo são as contribuições das últimas 30 semanas.
- assets/terminal.svg: terminal que digita quem sou, a stack e estatísticas.

Roda de hora em hora pelo GitHub Actions. Só usa a biblioteca padrão.
Para testar outros cenários: FORCAR_HORA=2026-10-28T21:00 FORCAR_CLIMA=61
"""
import json
import math
import os
import random
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

USUARIO = os.environ.get("GH_USER", "dev-renancosta")
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
NOME = "RENAN COSTA"
CARGO = "Estudante de Engenharia de Software"
BRT = timezone(timedelta(hours=-3))  # o Brasil não tem horário de verão desde 2019
LAT, LON = -26.9078, -48.6619  # Itajaí - SC
RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "assets"

W, H = 1000, 360
HORIZONTE = 272
SANS = "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif"
MONO = "Consolas, 'DejaVu Sans Mono', Menlo, 'Courier New', monospace"

DIAS_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
               "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]

# ---------------------------------------------------------------- dados

def get_json(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def clima(agora):
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}"
           "&current=temperature_2m,weather_code,cloud_cover"
           "&daily=sunrise,sunset&timezone=America%2FSao_Paulo&forecast_days=1")
    try:
        d = get_json(url)
        c = d["current"]
        cl = {
            "temp": round(c["temperature_2m"]),
            "codigo": c["weather_code"],
            "nuvens": c["cloud_cover"],
            "nascer": datetime.fromisoformat(d["daily"]["sunrise"][0]).replace(tzinfo=BRT),
            "por": datetime.fromisoformat(d["daily"]["sunset"][0]).replace(tzinfo=BRT),
        }
    except Exception as e:
        print("clima indisponível:", e)
        base = agora.replace(second=0, microsecond=0)
        cl = {"temp": None, "codigo": 1, "nuvens": 30,
              "nascer": base.replace(hour=5, minute=30), "por": base.replace(hour=18, minute=45)}
    if os.environ.get("FORCAR_CLIMA"):
        cl["codigo"] = int(os.environ["FORCAR_CLIMA"])
        cl["nuvens"] = 95 if cl["codigo"] >= 3 else 20
    return cl


def descricao(cod):
    if cod == 0:
        return "céu limpo"
    if cod in (1, 2):
        return "parcialmente nublado"
    if cod == 3:
        return "nublado"
    if cod in (45, 48):
        return "neblina"
    if 51 <= cod <= 57:
        return "garoa"
    if 61 <= cod <= 67 or 80 <= cod <= 82:
        return "chuva"
    if cod >= 95:
        return "tempestade"
    return "tempo instável"


def chovendo(cod):
    return 51 <= cod <= 67 or 80 <= cod <= 82 or cod >= 95


QUERY = """query($login: String!) { user(login: $login) {
  createdAt
  repositories(first: 8, privacy: PUBLIC, ownerAffiliations: OWNER, isFork: false,
               orderBy: {field: PUSHED_AT, direction: DESC}) {
    totalCount nodes { name url description primaryLanguage { name } } }
  contributionsCollection { contributionCalendar { totalContributions
    weeks { contributionDays { date contributionCount } } } } } }"""


def contribuicoes():
    if not TOKEN:
        print("sem token: usando prédios de exemplo")
        return None
    corpo = json.dumps({"query": QUERY, "variables": {"login": USUARIO}}).encode()
    try:
        u = get_json("https://api.github.com/graphql", corpo, {
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": USUARIO,
        })["data"]["user"]
    except Exception as e:
        print("GitHub indisponível:", e)
        return None
    cal = u["contributionsCollection"]["contributionCalendar"]
    return {
        "total": cal["totalContributions"],
        "dias": [(date.fromisoformat(d["date"]), d["contributionCount"])
                 for s in cal["weeks"] for d in s["contributionDays"]],
        "semanas": [sum(d["contributionCount"] for d in s["contributionDays"]) for s in cal["weeks"]],
        "repos": u["repositories"]["totalCount"],
        "projetos": [{"nome": r["name"], "url": r["url"], "descricao": r["description"] or "",
                      "lingua": (r["primaryLanguage"] or {}).get("name", "")}
                     for r in u["repositories"]["nodes"] if r["name"] != USUARIO][:6],
        "desde": datetime.fromisoformat(u["createdAt"].replace("Z", "+00:00")),
    }


def estatisticas(c, hoje):
    if not c:
        return None
    contagem = dict(c["dias"])
    d = hoje if contagem.get(hoje, 0) else hoje - timedelta(days=1)
    atual = 0
    while contagem.get(d, 0):
        atual += 1
        d -= timedelta(days=1)
    recorde = seguidos = 0
    for _, n in c["dias"]:
        seguidos = seguidos + 1 if n else 0
        recorde = max(recorde, seguidos)
    por_dia = [0] * 7
    for d, n in c["dias"]:
        por_dia[d.weekday()] += n
    ativos = [d for d, n in c["dias"] if n]
    if ativos:
        dias = (hoje - max(ativos)).days
        ultima = "hoje" if dias <= 0 else "ontem" if dias == 1 else f"há {dias} dias"
    else:
        ultima = "n/d"
    return {
        "total": c["total"], "atual": atual, "recorde": recorde, "ultima": ultima,
        "melhor": DIAS_SEMANA[por_dia.index(max(por_dia))],
        "desde": f"{MESES[c['desde'].month - 1]} de {c['desde'].year}",
        "repos": c["repos"],
    }


# ---------------------------------------------------------------- header

CEU = {
    "noite": ("#050816", "#111a38", "#223062"),
    "amanhecer": ("#26305e", "#b8668a", "#f8b195"),
    "dia": ("#1f6fca", "#4f9fe6", "#b6deff"),
    "entardecer": ("#291d4d", "#bf4778", "#ffb169"),
}
PREDIOS = {"noite": "#0e1530", "amanhecer": "#3a2d58", "dia": "#3a5f86", "entardecer": "#3a2350"}
SILHUETA = {"noite": "#04060e", "amanhecer": "#1c1736", "dia": "#18304d", "entardecer": "#1c112e"}
AGUA = {"noite": ("#0b1430", "#02040b"), "amanhecer": ("#59496f", "#1a1533"),
        "dia": ("#2b6aa6", "#0f3157"), "entardecer": ("#6b2f5d", "#1a0f2c")}
CAPACIDADE_NAVIO = 42  # 14 colunas x 3 andares
CONTEINERES = ["#c0392b", "#2e86c1", "#d68910", "#239b56", "#7d3c98", "#a6acaf", "#16a085"]

CSS_HEADER = """
.tw{animation:tw 3s ease-in-out infinite}
@keyframes tw{0%,100%{opacity:.2}50%{opacity:1}}
.nuvem{animation:drift linear infinite}
@keyframes drift{from{transform:translateX(-380px)}to{transform:translateX(1380px)}}
.onda{animation:onda linear infinite}
@keyframes onda{from{transform:translateX(0)}to{transform:translateX(-80px)}}
.navio{animation:navio 110s linear infinite}
@keyframes navio{from{transform:translateX(-300px)}to{transform:translateX(1100px)}}
.barco{animation:barco 70s linear infinite}
@keyframes barco{from{transform:translateX(1080px)}to{transform:translateX(-120px)}}
.balanca{animation:balanca 4s ease-in-out infinite}
@keyframes balanca{0%,100%{transform:translateY(0)}50%{transform:translateY(1.6px)}}
.pisca{animation:pisca 1.8s steps(1) infinite}
@keyframes pisca{0%{opacity:1}50%{opacity:.1}}
.janela{animation:janela 9s steps(1) infinite}
@keyframes janela{0%{opacity:.95}62%{opacity:.2}80%{opacity:.95}}
.chuva{animation:chuva .65s linear infinite}
@keyframes chuva{from{transform:translateY(-360px)}to{transform:translateY(0)}}
.flash{animation:flash 9s infinite}
@keyframes flash{0%,90%,100%{opacity:0}91%{opacity:.55}93%{opacity:0}94%{opacity:.35}96%{opacity:0}}
.ave{animation:ave 50s linear infinite}
@keyframes ave{from{transform:translate(-80px,0)}to{transform:translate(1080px,-40px)}}
.entra{animation:entra 1.2s ease-out both}
@keyframes entra{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
.d1{animation-delay:.3s}.d2{animation-delay:.6s}.d3{animation-delay:.9s}
"""


def mix(a, b, t):
    a = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def fase(agora, nascer, por):
    margem = timedelta(minutes=40)
    if abs(agora - nascer) <= margem:
        return "amanhecer"
    if abs(agora - por) <= margem:
        return "entardecer"
    return "dia" if nascer < agora < por else "noite"


def posicao_astro(agora, nascer, por):
    if nascer <= agora <= por:
        t = (agora - nascer) / (por - nascer)
    elif agora > por:
        t = (agora - por) / (nascer + timedelta(days=1) - por)
    else:
        t = (agora - (por - timedelta(days=1))) / (nascer - (por - timedelta(days=1)))
    return 90 + t * 820, HORIZONTE - 18 - math.sin(math.pi * t) * 200


def guindaste(x, cor, carga, duracao, atraso):
    """Portêiner visto de lado, com a lança sobre o rio (à esquerda)."""
    return f"""
  <g fill="{cor}" stroke="{cor}">
    <rect x="{x}" y="176" width="5" height="88"/><rect x="{x + 42}" y="176" width="5" height="88"/>
    <rect x="{x - 4}" y="214" width="55" height="4"/>
    <rect x="{x - 112}" y="170" width="190" height="7"/>
    <rect x="{x + 50}" y="158" width="26" height="12"/>
    <path d="M{x + 4} 170 L{x + 22} 132 L{x + 44} 170" fill="none" stroke-width="3"/>
    <path d="M{x + 22} 132 L{x - 110} 171 M{x + 22} 132 L{x + 76} 171" fill="none" stroke-width="1.2"/>
  </g>
  <g>
    <animateTransform attributeName="transform" type="translate" dur="{duracao}s" begin="{atraso}s"
      repeatCount="indefinite" values="0 0;-92 0;-92 0;0 0;0 0" keyTimes="0;.35;.5;.85;1"/>
    <rect x="{x + 10}" y="177" width="14" height="5" fill="{cor}"/>
    <line x1="{x + 17}" y1="182" x2="{x + 17}" y2="204" stroke="{cor}" stroke-width="1"/>
    <rect x="{x + 7}" y="204" width="20" height="8" fill="{carga}"/>
  </g>"""


def onda(y, amplitude, opacidade, duracao):
    d = f"M-40 {y} q10 {-amplitude} 20 0" + " t20 0" * 58
    return (f'<g class="onda" style="animation-duration:{duracao}s">'
            f'<path d="{d}" fill="none" stroke="#fff" stroke-opacity="{opacidade}" stroke-width="1.4"/></g>')


def svg_header(agora, cl, c):
    f = fase(agora, cl["nascer"], cl["por"])
    noite = f == "noite"
    fechado = chovendo(cl["codigo"]) or cl["nuvens"] >= 85 or cl["codigo"] in (45, 48)
    rnd = random.Random(agora.date().toordinal())
    ceu = [mix(cor, "#6b7685", .55) if fechado else cor for cor in CEU[f]]
    agua = [mix(cor, "#3b4552", .4) if fechado else cor for cor in AGUA[f]]
    silhueta, predio = SILHUETA[f], PREDIOS[f]
    p = []

    # estrelas
    if noite and not fechado:
        for _ in range(110):
            p.append(f'<circle class="tw" cx="{rnd.uniform(0, W):.0f}" cy="{rnd.uniform(0, 240):.0f}" '
                     f'r="{rnd.uniform(.5, 1.6):.1f}" fill="#fff" '
                     f'style="animation-delay:{rnd.uniform(0, 4):.1f}s;animation-duration:{rnd.uniform(2, 5):.1f}s"/>')

    # sol ou lua
    ax, ay = posicao_astro(agora, cl["nascer"], cl["por"])
    if not fechado:
        if noite:
            p.append(f'<circle cx="{ax:.0f}" cy="{ay:.0f}" r="40" fill="url(#halo)" opacity=".35"/>'
                     f'<circle cx="{ax:.0f}" cy="{ay:.0f}" r="17" fill="#f4f1de" mask="url(#crescente)"/>')
        else:
            p.append(f'<circle cx="{ax:.0f}" cy="{ay:.0f}" r="70" fill="url(#halo)"/>'
                     f'<circle cx="{ax:.0f}" cy="{ay:.0f}" r="22" fill="#fff4cf"/>')

    # nuvens
    for _ in range(min(8, round(cl["nuvens"] / 12))):
        y, s = rnd.uniform(20, 170), rnd.uniform(.7, 1.4)
        dur = rnd.uniform(90, 180)
        cor, op = ("#9aa6c4", .35) if noite else ("#ffffff", .8 if not fechado else .55)
        if fechado:
            cor = mix(cor, "#5d6775", .45)
        bolhas = "".join(f'<ellipse cx="{dx * s:.0f}" cy="{y + dy * s:.0f}" rx="{rx * s:.0f}" ry="{ry * s:.0f}"/>'
                         for dx, dy, rx, ry in ((0, 0, 46, 15), (32, -10, 30, 18), (64, 0, 40, 14), (-28, 4, 26, 10)))
        p.append(f'<g class="nuvem" fill="{cor}" opacity="{op}" '
                 f'style="animation-duration:{dur:.0f}s;animation-delay:-{rnd.uniform(0, dur):.0f}s">{bolhas}</g>')

    # gaivotas
    if f == "dia" and not chovendo(cl["codigo"]):
        for i in range(4):
            x0, y0 = i * 22 + rnd.uniform(0, 10), 90 + rnd.uniform(-12, 12) + i * 6
            p.append(f'<g class="ave" style="animation-delay:-{i * 3 + 8}s"><path d="M{x0:.0f} {y0:.0f} '
                     f'q5 -5 10 0 q5 -5 10 0" fill="none" stroke="{silhueta}" stroke-width="1.6"/></g>')

    # a cidade: um prédio por semana de contribuições
    semanas = c["semanas"][-30:] if c else [rnd.randint(0, 25) for _ in range(30)]
    maior = max(max(semanas), 1)
    largura = W / len(semanas)
    acesas = []
    for i, v in enumerate(semanas):
        h = 16 + math.sqrt(v / maior) * 145
        x, w, topo = i * largura + 3, largura - 6, HORIZONTE - h
        p.append(f'<rect x="{x:.1f}" y="{topo:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{predio}"/>'
                 f'<rect x="{x:.1f}" y="{topo:.1f}" width="{w:.1f}" height="{h:.1f}" fill="url(#janelas)"/>')
        if noite or f in ("amanhecer", "entardecer"):
            chance = .06 + .75 * v / maior
            for jx in range(math.ceil(x / 7), int((x + w - 5) / 7) + 1):
                for jy in range(math.ceil((topo + 4) / 10), int((HORIZONTE - 8) / 10) + 1):
                    if rnd.random() < chance:
                        classe = ' class="janela"' if rnd.random() < .12 else ""
                        acesas.append(f'<rect{classe} x="{jx * 7 + 2}" y="{jy * 10 + 3}" width="3" height="4" '
                                      f'style="animation-delay:-{rnd.uniform(0, 9):.1f}s"/>')
        if v == maior:
            p.append(f'<line x1="{x + w / 2:.1f}" y1="{topo:.1f}" x2="{x + w / 2:.1f}" y2="{topo - 18:.1f}" '
                     f'stroke="{predio}" stroke-width="2"/>'
                     f'<circle class="pisca" cx="{x + w / 2:.1f}" cy="{topo - 19:.1f}" r="2.2" fill="#ff4040"/>')
        if i == len(semanas) - 1:
            p.append(f'<circle class="pisca" cx="{x + w / 2:.1f}" cy="{topo - 3:.1f}" r="2" fill="#5ef0a0" '
                     f'style="animation-delay:.9s"/>')
    if acesas:
        p.append(f'<g fill="#ffd66b" opacity=".9">{"".join(acesas)}</g>')

    # cais, contêineres e guindastes
    p.append(f'<rect x="560" y="262" width="440" height="11" fill="{silhueta}"/>')
    escuro = .45 if noite else .1
    # um contêiner por commit nos últimos 14 dias: cada pilha é um dia (máx. 2 x 8)
    hoje = agora.date()
    contagem = dict(c["dias"]) if c else {hoje - timedelta(days=k): rnd.randint(0, 9) for k in range(15)}
    for i, k in enumerate(range(14, 0, -1)):
        for j in range(min(contagem.get(hoje - timedelta(days=k), 0), 16)):
            p.append(f'<rect x="{572 + i * 30 + (j % 2) * 13}" y="{253 - (j // 2) * 9}" width="12" height="8" '
                     f'fill="{mix(rnd.choice(CONTEINERES), silhueta, escuro)}"/>')
    for x, dur, atraso in ((690, 15, 0), (812, 18, -6), (934, 16, -11)):
        p.append(guindaste(x, silhueta, mix(rnd.choice(CONTEINERES), silhueta, escuro), dur, atraso))
    if noite:
        p.append("".join(f'<circle class="pisca" cx="{x + 22}" cy="131" r="2" fill="#ff4040" '
                         f'style="animation-delay:{k * .5}s"/>' for k, x in enumerate((690, 812, 934))))

    # rio
    p.append(f'<rect x="0" y="{HORIZONTE}" width="{W}" height="{H - HORIZONTE}" fill="url(#agua)"/>')
    if not fechado:
        brilho = "#f4f1de" if noite else "#ffe7a8"
        for k in range(7):
            lw = rnd.uniform(14, 46) * (1 - k / 10)
            p.append(f'<rect class="tw" x="{ax - lw / 2:.0f}" y="{HORIZONTE + 6 + k * 11}" width="{lw:.0f}" '
                     f'height="2" fill="{brilho}" opacity=".5" style="animation-delay:{k * .4:.1f}s"/>')
    for k in range(5):
        p.append(onda(HORIZONTE + 10 + k * 17, 1.5 + k * .6, .07 + k * .03, 6 + k * 2))

    # navios: levam os commits de hoje, um contêiner por commit. Encheu, entra outro.
    casco = SILHUETA["noite"] if noite else "#1b2333"
    luzes = ('<g fill="#ffd66b"><rect x="11" y="-34" width="20" height="3"/>'
             '<circle cx="246" cy="-12" r="1.6"/><circle cx="4" cy="-8" r="1.6"/></g>') if noite else \
        '<rect x="11" y="-34" width="20" height="3" fill="#1b2333"/>'
    ponte = SILHUETA["noite"] if noite else "#dfe3ea"
    restante = contagem.get(hoje, 0)
    cargas = []
    while restante > 0 and len(cargas) < 3:
        cargas.append(min(restante, CAPACIDADE_NAVIO))
        restante -= cargas[-1]
    cargas = cargas or [0]  # sem commits hoje, o navio passa vazio
    # (faixa y, escala, duração): o segundo navio vai mais ao fundo e mais devagar
    faixas = [(296, 1, 110), (284, .72, 150), (296, 1, 110)]
    navios = []
    for k, carga in enumerate(cargas):
        y, escala, dur = faixas[k]
        cont = "".join(f'<rect x="{44 + (j % 14) * 13}" y="{-13 - (j // 14) * 7}" width="12" height="6" '
                       f'fill="{mix(rnd.choice(CONTEINERES), casco, escuro)}"/>' for j in range(carga))
        atraso = (agora.minute / 60 * dur + k * dur / 2) % dur
        navios.append(f"""<g class="navio" style="animation-duration:{dur}s;animation-delay:-{atraso:.0f}s"><g class="balanca">
  <g transform="translate(0 {y}) scale({escala})">
    <polygon points="0,-6 236,-6 250,-14 238,12 10,12" fill="{casco}"/>
    <rect x="9" y="6" width="232" height="6" fill="#8b2c2c"/>
    {cont}<rect x="8" y="-38" width="26" height="32" fill="{ponte}"/>
    <rect x="14" y="-46" width="7" height="8" fill="#8b2c2c"/>{luzes}
  </g></g></g>""")
    if len(navios) > 1:  # o navio do fundo é desenhado antes para ficar atrás
        navios[0], navios[1] = navios[1], navios[0]
    p.extend(navios)

    # barco de pesca (Itajaí é um dos maiores portos pesqueiros do país)
    barco = SILHUETA["noite"] if noite else "#e8ecf1"
    p.append(f"""<g class="barco" style="animation-delay:-{(agora.minute * 7) % 70}s"><g class="balanca"><g transform="translate(0 326)">
    <polygon points="0,-3 62,-3 56,8 6,8" fill="{barco}"/>
    <rect x="34" y="-16" width="16" height="13" fill="{barco}"/>
    <line x1="18" y1="-3" x2="18" y2="-30" stroke="{silhueta}" stroke-width="1.5"/>
    <line x1="18" y1="-28" x2="-6" y2="-6" stroke="{silhueta}" stroke-width="1"/>
    {'<circle cx="18" cy="-31" r="1.8" fill="#ffd66b"/>' if noite else ''}
  </g></g></g>""")

    # chuva, raios e neblina
    if chovendo(cl["codigo"]):
        gotas = []
        for _ in range(140):
            x, y = rnd.uniform(0, W + 40), rnd.uniform(0, 360)
            for dy in (0, 360):
                gotas.append(f'<line x1="{x:.0f}" y1="{y + dy:.0f}" x2="{x - 4:.0f}" y2="{y + dy + 13:.0f}"/>')
        p.append(f'<g class="chuva" stroke="#c8d8ff" stroke-opacity=".45" stroke-width="1">{"".join(gotas)}</g>')
    if cl["codigo"] >= 95:
        p.append(f'<rect class="flash" width="{W}" height="{H}" fill="#fff"/>')
    if cl["codigo"] in (45, 48):
        p.append(f'<rect width="{W}" height="{H}" fill="url(#neblina)"/>')

    # textos
    hora = agora.strftime("%Hh%M")
    saudacao = "Bom dia" if 5 <= agora.hour < 12 else "Boa tarde" if 12 <= agora.hour < 18 else "Boa noite"
    tempo = f"{cl['temp']}°C · {descricao(cl['codigo'])}" if cl["temp"] is not None else descricao(cl["codigo"])
    p.append(f"""<g class="entra"><rect x="24" y="24" width="560" height="152" rx="14" fill="#060a18"
      fill-opacity=".58" stroke="#fff" stroke-opacity=".14"/></g>
  <text class="entra" x="48" y="80" font-family="{SANS}" font-size="46" font-weight="800" letter-spacing="5"
    fill="url(#brilho)">{escape(NOME)}</text>
  <text class="entra d1" x="50" y="109" font-family="{SANS}" font-size="17" fill="#cfe3ff">{escape(CARGO)}</text>
  <text class="entra d2" x="50" y="139" font-family="{MONO}" font-size="13.5" fill="#fff">
    <tspan fill="#7ee787">●</tspan> {saudacao} de Itajaí - SC · {hora} · {escape(tempo)}</text>
  <text class="entra d3" x="50" y="160" font-family="{SANS}" font-size="11.5" fill="#fff" fill-opacity=".62">prédios: minhas semanas de código · contêineres: meus commits · navio: hoje</text>
  <text x="{W - 14}" y="{H - 10}" text-anchor="end" font-family="{MONO}" font-size="10" fill="#fff"
    fill-opacity=".45">atualizado {agora.strftime('%d/%m %Hh%M')}</text>""")

    lua_x, lua_y = round(ax), round(ay)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img"
  aria-label="Porto de Itajaí agora: {saudacao.lower()}, {escape(tempo)}">
<title>{escape(NOME)}: porto de Itajaí agora, {escape(tempo)}</title>
<style><![CDATA[{CSS_HEADER}]]></style>
<defs>
  <clipPath id="moldura"><rect width="{W}" height="{H}" rx="16"/></clipPath>
  <linearGradient id="ceu" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{ceu[0]}"/><stop offset=".6" stop-color="{ceu[1]}"/><stop offset="1" stop-color="{ceu[2]}"/>
  </linearGradient>
  <linearGradient id="agua" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{agua[0]}"/><stop offset="1" stop-color="{agua[1]}"/>
  </linearGradient>
  <linearGradient id="neblina" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#dfe5ec" stop-opacity=".15"/><stop offset=".8" stop-color="#dfe5ec" stop-opacity=".55"/>
  </linearGradient>
  <radialGradient id="halo">
    <stop offset="0" stop-color="#fff2c4" stop-opacity=".9"/><stop offset=".35" stop-color="#ffd36b" stop-opacity=".45"/>
    <stop offset="1" stop-color="#ffd36b" stop-opacity="0"/>
  </radialGradient>
  <mask id="crescente"><circle cx="{lua_x}" cy="{lua_y}" r="17" fill="#fff"/>
    <circle cx="{lua_x + 8}" cy="{lua_y - 5}" r="14" fill="#000"/></mask>
  <pattern id="janelas" width="7" height="10" patternUnits="userSpaceOnUse">
    <rect x="2" y="3" width="3" height="4" fill="#fff" fill-opacity="{.05 if noite else .16}"/>
  </pattern>
  <linearGradient id="brilho" x1="0" y1="0" x2="1" y2="0" spreadMethod="repeat">
    <stop offset="0" stop-color="#ffffff"/><stop offset=".45" stop-color="#ffffff"/>
    <stop offset=".5" stop-color="#8fd3ff"/><stop offset=".55" stop-color="#ffffff"/><stop offset="1" stop-color="#ffffff"/>
    <animateTransform attributeName="gradientTransform" type="translate" from="-1 0" to="1 0" dur="5s" repeatCount="indefinite"/>
  </linearGradient>
</defs>
<g clip-path="url(#moldura)">
<rect width="{W}" height="{H}" fill="url(#ceu)"/>
{chr(10).join(p)}
</g>
</svg>
"""


# ---------------------------------------------------------------- terminal

TW, CW, LH, X0 = 1000, 9.03, 24, 28  # largura, largura do caractere, altura da linha, margem
CORES = {"txt": "#c9d1d9", "cinza": "#8b949e", "verde": "#7ee787", "azul": "#79c0ff",
         "claro": "#a5d6ff", "amarelo": "#e3b341", "branco": "#ffffff", "laranja": "#ffa657"}
PROMPT = [("renan@costa", "verde"), (":", "txt"), ("~", "azul"), ("$ ", "txt")]


def svg_terminal(agora, est, projetos):
    def v(chave, sufixo=""):
        return f"{est[chave]}{sufixo}" if est else "n/d"

    def stat(rotulo, valor, extra=""):
        return [("● ", "verde"), (f"{rotulo} {'.' * (30 - len(rotulo))} ", "cinza"), (valor, "branco"),
                (extra, "cinza")]

    aprendizado = [("estudando", ["Engenharia de Software", "Estruturas de Dados", "Inteligência Artificial"]),
                   ("praticando", ["React", "TypeScript", "Python", "Django", "FastAPI"]),
                   ("explorando", ["Docker", "Linux", "PostgreSQL", "Nginx"])]
    json_linhas = [("out", [("{", "txt")])]
    for i, (chave, itens) in enumerate(aprendizado):
        json_linhas.append(("out", [(f'  "{chave}"', "azul"), (": [", "txt")]))
        json_linhas += [("out", [(f'    "{item}"', "claro"), ("," if k < len(itens) - 1 else "", "txt")])
                        for k, item in enumerate(itens)]
        json_linhas.append(("out", [("  ]" + ("," if i < len(aprendizado) - 1 else ""), "txt")]))
    json_linhas.append(("out", [("}", "txt")]))
    roteiro = [
        ("cmd", "whoami"),
        ("out", [("Renan Costa", "branco")]),
        ("out", [("Estudante de Engenharia de Software", "txt")]),
        ("out", [("Desenvolvendo projetos, explorando tecnologias e aprendendo um commit de cada vez.", "cinza")]),
        ("cmd", "cat aprendizado.json"),
        *json_linhas,
        ("cmd", "ls ~/projetos"),
        *[("out", [("▸ ", "verde"), (pr["nome"], "azul"), (f" {'.' * max(2, 44 - len(pr['nome']))} ", "cinza"),
                   (pr["lingua"] or "n/d", "claro")]) for pr in projetos],
        ("cmd", "./status --ao-vivo"),
        ("out", stat("contribuições no último ano", v("total"))),
        ("out", stat("sequência atual", v("atual", " dias"), f"   (recorde: {v('recorde', ' dias')})")),
        ("out", stat("última atividade", v("ultima"))),
        ("out", stat("dia mais produtivo", v("melhor"))),
        ("out", stat("projetos públicos", v("repos"))),
        ("out", stat("no GitHub desde", v("desde"))),
        ("cmd", "cat lema.txt"),
        ("out", [("O código funciona. Não faça perguntas.", "verde")]),
    ]

    def tspans(segmentos):
        return "".join(f'<tspan fill="{CORES[c]}"{" font-weight=\"700\"" if c == "branco" else ""}>'
                       f'{escape(t)}</tspan>' for t, c in segmentos)

    corpo, defs = [], []
    t, y = .6, 70
    for i, (tipo, conteudo) in enumerate(roteiro):
        if tipo == "cmd":
            if i:
                y += 10
            n_prompt = sum(len(s) for s, _ in PROMPT)
            passos = [round((n_prompt + k) * CW, 1) for k in range(len(conteudo) + 1)]
            dur = len(conteudo) * .07
            defs.append(f'<clipPath id="c{i}"><rect x="0" y="{y - 18}" width="{X0 + passos[0]}" height="{LH}">'
                        f'<animate attributeName="width" begin="{t + .35:.2f}s" dur="{dur:.2f}s" fill="freeze" '
                        f'calcMode="discrete" values="{";".join(str(X0 + s) for s in passos)}"/></rect></clipPath>')
            corpo.append(f'<g opacity="0"><set attributeName="opacity" to="1" begin="{t:.2f}s" fill="freeze"/>'
                         f'<text x="{X0}" y="{y}" clip-path="url(#c{i})">{tspans(PROMPT + [(conteudo, "branco")])}'
                         f'</text></g>')
            t += .35 + dur + .35
        else:
            # espaços no início somem dentro de <img>, então a indentação vira deslocamento em x
            recuo = len(conteudo[0][0]) - len(conteudo[0][0].lstrip(" "))
            conteudo = [(conteudo[0][0].lstrip(" "), conteudo[0][1])] + conteudo[1:]
            corpo.append(f'<g opacity="0"><set attributeName="opacity" to="1" begin="{t:.2f}s" fill="freeze"/>'
                         f'<text x="{X0 + recuo * CW:.0f}" y="{y}">{tspans(conteudo)}</text></g>')
            t += .09
        y += LH
    y += 10
    corpo.append(f'<g opacity="0"><set attributeName="opacity" to="1" begin="{t + .3:.2f}s" fill="freeze"/>'
                 f'<text x="{X0}" y="{y}">{tspans(PROMPT)}</text>'
                 f'<rect x="{X0 + sum(len(s) for s, _ in PROMPT) * CW:.0f}" y="{y - 15}" width="9" height="19" fill="{CORES["verde"]}">'
                 f'<animate attributeName="opacity" values="1;0;1" dur="1.1s" calcMode="discrete" '
                 f'repeatCount="indefinite"/></rect></g>')
    altura = y + 26

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {TW} {altura}" width="{TW}" height="{altura}" role="img"
  aria-label="Terminal: quem sou, minha stack e estatísticas ao vivo">
<title>renan@costa: ~</title>
<defs>{"".join(defs)}</defs>
<rect x=".5" y=".5" width="{TW - 1}" height="{altura - 1}" rx="14" fill="#0d1117" stroke="#30363d"/>
<path d="M14.5 .5 H{TW - 14.5} a14 14 0 0 1 14 14 V38 H.5 V14.5 a14 14 0 0 1 14 -14z" fill="#161b22"/>
<line x1=".5" y1="38" x2="{TW - .5}" y2="38" stroke="#30363d"/>
<circle cx="24" cy="19" r="6" fill="#ff5f56"/><circle cx="44" cy="19" r="6" fill="#ffbd2e"/><circle cx="64" cy="19" r="6" fill="#27c93f"/>
<text x="{TW / 2}" y="24" text-anchor="middle" font-family="{MONO}" font-size="13" fill="#8b949e">renan@costa: ~ · zsh</text>
<g font-family="{MONO}" font-size="15" xml:space="preserve" style="white-space:pre">
{chr(10).join(corpo)}
</g>
</svg>
"""


# ---------------------------------------------------------------- README

def atualizar_readme(projetos):
    """Imagens em <img> não têm links, então a lista clicável fica no próprio README."""
    readme = RAIZ / "README.md"
    texto = readme.read_text(encoding="utf-8")
    inicio, fim = "<!-- projetos:inicio -->", "<!-- projetos:fim -->"
    if inicio not in texto or fim not in texto:
        return
    linhas = ["| Projeto | Linguagem | Sobre |", "| --- | --- | --- |"]
    linhas += [f"| [**{pr['nome']}**]({pr['url']}) | {pr['lingua']} | {pr['descricao']} |" for pr in projetos]
    antes, resto = texto.split(inicio, 1)
    tabela = "\n".join(linhas)
    texto = f"{antes}{inicio}\n{tabela}\n{fim}{resto.split(fim, 1)[1]}"
    readme.write_text(texto, encoding="utf-8")


# ---------------------------------------------------------------- main

def main():
    agora = datetime.now(BRT)
    if os.environ.get("FORCAR_HORA"):
        agora = datetime.fromisoformat(os.environ["FORCAR_HORA"]).replace(tzinfo=BRT)
    cl = clima(agora)
    if os.environ.get("FORCAR_HORA"):
        cl["nascer"] = cl["nascer"].replace(year=agora.year, month=agora.month, day=agora.day)
        cl["por"] = cl["por"].replace(year=agora.year, month=agora.month, day=agora.day)
    c = contribuicoes()
    SAIDA.mkdir(exist_ok=True)
    (SAIDA / "header.svg").write_text(svg_header(agora, cl, c), encoding="utf-8")
    (SAIDA / "terminal.svg").write_text(svg_terminal(agora, estatisticas(c, agora.date()), c["projetos"] if c else []), encoding="utf-8")
    if c:
        atualizar_readme(c["projetos"])
    print(f"ok: {agora:%d/%m %H:%M}, {descricao(cl['codigo'])}, {fase(agora, cl['nascer'], cl['por'])}")


if __name__ == "__main__":
    main()
