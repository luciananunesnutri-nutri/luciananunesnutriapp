"""
Luciana Nunes Nutri — Sistema de gestão nutricional.
"""
import sqlite3
import os
from flask import Flask, render_template, request, jsonify, g, redirect
from datetime import datetime

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "avanutri.db")

NOMES_REFEICAO = {
    "0": "Desjejum", "1": "Desjejum", "2": "Colação", "3": "Almoço",
    "4": "Lanche da Tarde", "5": "Jantar", "6": "Ceia",
    "7": "Lanche Extra 1", "8": "Lanche Extra 2", "9": "Lanche Extra 3",
}


def to_float(val):
    if val is None or val == "":
        return 0.0
    try:
        if isinstance(val, str):
            val = val.replace(",", ".")
        return float(val)
    except (ValueError, TypeError):
        return 0.0


@app.template_filter("num")
def num_filter(value, decimals=1):
    if value is None or value == "":
        return "—"
    try:
        if isinstance(val := value, str):
            val = val.replace(",", ".")
        return f"{float(val):.{decimals}f}"
    except (ValueError, TypeError):
        return "—"


@app.template_filter("data")
def data_filter(value):
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(str(value).replace("T", " "))
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return str(value)[:10] if len(str(value)) >= 10 else str(value)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA cache_size=-8000")
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def calc_idade(dt_nasc_str):
    if not dt_nasc_str:
        return None
    try:
        dt = datetime.fromisoformat(str(dt_nasc_str).replace("T", " "))
        hoje = datetime.now()
        return hoje.year - dt.year - ((hoje.month, hoje.day) < (dt.month, dt.day))
    except Exception:
        return None


def calc_idade_detalhada(dt_nasc_str):
    if not dt_nasc_str:
        return "—"
    try:
        dt = datetime.fromisoformat(str(dt_nasc_str).replace("T", " "))
        hoje = datetime.now()
        anos = hoje.year - dt.year
        meses = hoje.month - dt.month
        if hoje.day < dt.day:
            meses -= 1
        if meses < 0:
            anos -= 1
            meses += 12
        if anos < 0:
            return "—"
        if anos == 0 and meses == 0:
            dias = (hoje - dt.replace(year=hoje.year, month=hoje.month)).days
            if dias < 0:
                dias = (hoje - dt).days
            return f"{dias}d"
        if anos == 0:
            return f"{meses}m"
        if anos < 5:
            return f"{anos}a {meses}m"
        return f"{anos}a"
    except Exception:
        return "—"


def calc_imc(peso, estatura):
    p = to_float(peso)
    e = to_float(estatura)
    if p == 0 or e == 0:
        return None
    alt_m = e / 100.0 if e > 3 else e
    if alt_m == 0:
        return None
    return round(p / (alt_m * alt_m), 2)


def classif_imc(imc):
    if imc is None:
        return ("", "")
    if imc < 18.5:
        return ("Abaixo do peso", "info")
    if imc < 25:
        return ("Eutrófico", "success")
    if imc < 30:
        return ("Pré-Obeso", "warning")
    if imc < 35:
        return ("Obesidade Grau I", "danger")
    if imc < 40:
        return ("Obesidade Grau II", "danger")
    return ("Obesidade Grau III", "danger")


def peso_saudavel(estatura):
    e = to_float(estatura)
    if e == 0:
        return None, None
    alt_m = e / 100.0 if e > 3 else e
    return round(18.5 * alt_m * alt_m, 1), round(24.9 * alt_m * alt_m, 1)


def pct_alteracao_peso(peso_atual, peso_usual):
    pa = to_float(peso_atual)
    pu = to_float(peso_usual)
    if pu == 0:
        return None
    return round(((pa - pu) / pu) * 100, 2)


# --- ROUTES ---

@app.route("/")
def index():
    db = get_db()
    busca = request.args.get("q", "").strip()
    stats = {
        "pacientes": db.execute("SELECT COUNT(*) FROM paciente").fetchone()[0],
        "alimentos": db.execute("SELECT COUNT(*) FROM alimento").fetchone()[0],
        "receitas": db.execute("SELECT COUNT(*) FROM receita").fetchone()[0],
        "cardapios": db.execute("SELECT COUNT(*) FROM cardapio").fetchone()[0],
        "antropometrias": db.execute("SELECT COUNT(*) FROM antropometria").fetchone()[0],
        "condutas": db.execute("SELECT COUNT(*) FROM conduta_nutricional").fetchone()[0],
        "protocolos": db.execute("SELECT COUNT(*) FROM protocolo_paciente").fetchone()[0],
    }
    if busca:
        pacientes_recentes = db.execute("""
            SELECT p.Cd_Paciente, p.Nm_Paciente, p.Fl_Sexo, p.Dt_Nascimento, p.Dt_Alteracao,
                   pp_agg.Dt_Ultimo_Atendimento
            FROM paciente p
            LEFT JOIN (SELECT Cd_Paciente, MAX(Dt_Atendimento) AS Dt_Ultimo_Atendimento
                       FROM protocolo_paciente GROUP BY Cd_Paciente) pp_agg
                ON pp_agg.Cd_Paciente = p.Cd_Paciente
            WHERE p.Nm_Paciente LIKE ? OR p.Nr_Tel_Cel LIKE ?
            ORDER BY p.Nm_Paciente LIMIT 20
        """, (f"%{busca}%", f"%{busca}%")).fetchall()
    else:
        pacientes_recentes = db.execute("""
            SELECT p.Cd_Paciente, p.Nm_Paciente, p.Fl_Sexo, p.Dt_Nascimento, p.Dt_Alteracao,
                   pp_agg.Dt_Ultimo_Atendimento
            FROM paciente p
            LEFT JOIN (SELECT Cd_Paciente, MAX(Dt_Atendimento) AS Dt_Ultimo_Atendimento
                       FROM protocolo_paciente GROUP BY Cd_Paciente) pp_agg
                ON pp_agg.Cd_Paciente = p.Cd_Paciente
            ORDER BY p.Dt_Alteracao DESC LIMIT 15
        """).fetchall()
    return render_template("index.html", stats=stats,
        pacientes_recentes=pacientes_recentes, calc_idade=calc_idade,
        calc_idade_detalhada=calc_idade_detalhada, busca=busca)


@app.route("/pacientes")
def pacientes():
    db = get_db()
    busca = request.args.get("q", "").strip()
    page = int(request.args.get("page", 1))
    per_page = 50
    params = []
    where = ""
    if busca:
        where = "WHERE Nm_Paciente LIKE ? OR Ds_email LIKE ? OR Nr_Tel_Cel LIKE ?"
        params = [f"%{busca}%"] * 3
    ordenar = request.args.get("ordenar", "nome")
    direcao = request.args.get("dir", "asc")
    if direcao not in ("asc", "desc"):
        direcao = "asc"
    order_map = {
        "nome": "p.Nm_Paciente",
        "ultimo_atendimento": "Dt_Ultimo_Atendimento",
    }
    order_col = order_map.get(ordenar, "p.Nm_Paciente")
    nulls = " NULLS LAST" if direcao == "desc" else " NULLS LAST"

    qual_where = where.replace('Nm_Paciente','p.Nm_Paciente').replace('Ds_email','p.Ds_email').replace('Nr_Tel_Cel','p.Nr_Tel_Cel')
    total = db.execute(f"SELECT COUNT(*) FROM paciente p {qual_where}", params).fetchone()[0]
    rows = db.execute(f"""
        SELECT p.Cd_Paciente, p.Nm_Paciente, p.Fl_Sexo, p.Dt_Nascimento,
               p.Nr_Tel_Cel, p.Dt_Alteracao,
               pp_agg.Dt_Ultimo_Atendimento,
               pp_agg.Qt_Atendimentos
        FROM paciente p
        LEFT JOIN (SELECT Cd_Paciente,
                          MAX(Dt_Atendimento) AS Dt_Ultimo_Atendimento,
                          COUNT(*) AS Qt_Atendimentos
                   FROM protocolo_paciente GROUP BY Cd_Paciente) pp_agg
            ON pp_agg.Cd_Paciente = p.Cd_Paciente
        {qual_where}
        ORDER BY {order_col} {direcao} {nulls} LIMIT ? OFFSET ?
    """, params + [per_page, (page - 1) * per_page]).fetchall()
    total_pages = max(1, (total + per_page - 1) // per_page)
    return render_template("pacientes.html", pacientes=rows, busca=busca,
        page=page, total_pages=total_pages, total=total,
        calc_idade=calc_idade, calc_idade_detalhada=calc_idade_detalhada,
        ordenar=ordenar, direcao=direcao)


@app.route("/paciente/<int:cd_paciente>")
def paciente_detalhe(cd_paciente):
    return paciente_secao(cd_paciente, "resumo")


@app.route("/paciente/<int:cd_paciente>/<secao>")
def paciente_secao(cd_paciente, secao="resumo"):
    db = get_db()
    pac = db.execute("SELECT * FROM paciente WHERE Cd_Paciente = ?", (cd_paciente,)).fetchone()
    if not pac:
        return "Paciente não encontrado", 404

    idade = calc_idade(pac["Dt_Nascimento"])
    context = dict(pac=pac, secao=secao, idade=idade,
                   calc_idade=calc_idade, calc_imc=calc_imc,
                   classif_imc=classif_imc, to_float=to_float)

    if secao == "resumo":
        protocolos = db.execute("""
            SELECT pp.*,
                (SELECT COUNT(*) FROM antropometria a
                 WHERE a.Cd_Paciente = pp.Cd_Paciente AND a.Nr_Protocolo = pp.Nr_Protocolo) AS qt_antrop,
                (SELECT COUNT(*) FROM conduta_nutricional cn
                 WHERE cn.CD_PACIENTE = pp.Cd_Paciente AND cn.NR_PROTOCOLO = pp.Nr_Protocolo) AS qt_conduta,
                (SELECT COUNT(*) FROM anamnese_nutricional an
                 WHERE an.CD_PACIENTE = pp.Cd_Paciente AND an.NR_PROTOCOLO = pp.Nr_Protocolo) AS qt_anamnese
            FROM protocolo_paciente pp
            WHERE pp.Cd_Paciente = ? ORDER BY pp.Nr_Protocolo DESC
        """, (cd_paciente,)).fetchall()
        ultima_antrop = db.execute("""
            SELECT * FROM antropometria
            WHERE Cd_Paciente = ? ORDER BY Nr_Protocolo DESC LIMIT 1
        """, (cd_paciente,)).fetchone()
        condutas = db.execute("""
            SELECT cn.*, pp.Dt_Atendimento
            FROM conduta_nutricional cn
            LEFT JOIN protocolo_paciente pp
                ON cn.CD_PACIENTE = pp.Cd_Paciente AND cn.NR_PROTOCOLO = pp.Nr_Protocolo
            WHERE cn.CD_PACIENTE = ? ORDER BY cn.NR_PROTOCOLO DESC LIMIT 3
        """, (cd_paciente,)).fetchall()
        proto_details = {}
        for p in protocolos:
            nr = p["Nr_Protocolo"]
            details = {}
            antrop = db.execute("""
                SELECT Vl_Peso_Atual, Vl_Estatura, Vl_Perim_Cintura, Vl_Circunf_Braco,
                       Vl_Prega_Tricipital, Vl_Prega_Subescapular, Vl_Pct_Gord_Bio
                FROM antropometria WHERE Cd_Paciente = ? AND Nr_Protocolo = ?
            """, (cd_paciente, nr)).fetchone()
            if antrop:
                details["antrop"] = antrop
            conduta = db.execute("""
                SELECT TX_COND_NUTRI FROM conduta_nutricional
                WHERE CD_PACIENTE = ? AND NR_PROTOCOLO = ?
            """, (cd_paciente, nr)).fetchone()
            if conduta:
                details["conduta"] = conduta["TX_COND_NUTRI"]
            anamnese = db.execute("""
                SELECT an.CD_TIPO, a.Nm_Alimento, m.Ds_Medida, an.QT_ALIMENTO
                FROM anamnese_nutricional an
                LEFT JOIN alimento a ON an.CD_ALIMENTO = a.cd_alimento
                LEFT JOIN medida m ON an.CD_MEDIDA = m.Cd_Medida
                WHERE an.CD_PACIENTE = ? AND an.NR_PROTOCOLO = ?
                ORDER BY an.CD_TIPO, an.DT_HORA
            """, (cd_paciente, nr)).fetchall()
            if anamnese:
                details["anamnese"] = anamnese
            recomendacao = db.execute("""
                SELECT * FROM recomendacao_nutricional
                WHERE CD_PACIENTE = ? AND NR_PROTOCOLO = ?
            """, (cd_paciente, nr)).fetchone()
            if recomendacao:
                details["recomendacao"] = recomendacao
            proto_details[nr] = details
        context.update(protocolos=protocolos, ultima_antrop=ultima_antrop,
                       condutas=condutas, proto_details=proto_details)

    elif secao == "antropometria":
        antropometrias = db.execute("""
            SELECT a.*, p.DS_PROTOCOLO
            FROM antropometria a
            LEFT JOIN protocolo p ON a.Cd_Protocolo = p.CD_PROTOCOLO
            WHERE a.Cd_Paciente = ? ORDER BY a.Nr_Protocolo DESC
        """, (cd_paciente,)).fetchall()
        context.update(antropometrias=antropometrias,
                       peso_saudavel=peso_saudavel,
                       pct_alteracao_peso=pct_alteracao_peso)

    elif secao == "laboratorial":
        grupos = db.execute("SELECT * FROM grupo_exame ORDER BY CD_GRUPO").fetchall()
        exames = db.execute("SELECT * FROM exame_bioquimico ORDER BY CD_GRUPO_EXAME, NM_EXAME").fetchall()
        context.update(grupos=grupos, exames=exames)

    elif secao == "estudo_alimentar":
        registros = db.execute("""
            SELECT an.*, a.Nm_Alimento, m.Ds_Medida
            FROM anamnese_nutricional an
            LEFT JOIN alimento a ON an.CD_ALIMENTO = a.cd_alimento
            LEFT JOIN medida m ON an.CD_MEDIDA = m.Cd_Medida
            WHERE an.CD_PACIENTE = ?
            ORDER BY an.NR_PROTOCOLO DESC, an.DT_HORA
        """, (cd_paciente,)).fetchall()
        refeicoes_por_protocolo = {}
        for r in registros:
            proto = r["NR_PROTOCOLO"]
            if proto not in refeicoes_por_protocolo:
                refeicoes_por_protocolo[proto] = {}
            tp = str(r["CD_TIPO"]) if r["CD_TIPO"] is not None else "0"
            nome_ref = NOMES_REFEICAO.get(tp, f"Refeição {tp}")
            if nome_ref not in refeicoes_por_protocolo[proto]:
                refeicoes_por_protocolo[proto][nome_ref] = []
            refeicoes_por_protocolo[proto][nome_ref].append(r)
        context.update(refeicoes_por_protocolo=refeicoes_por_protocolo,
                       NOMES_REFEICAO=NOMES_REFEICAO)

    elif secao == "prescricao":
        cardapios_pac = db.execute("""
            SELECT ic.*, a.Nm_Alimento, m.Ds_Medida, c.DS_CARDAPIO,
                   ic.CD_CARDAPIO, ic.TP_REFEICAO
            FROM itens_cardapio ic
            JOIN alimento a ON ic.CD_ALIMENTO = a.cd_alimento
            LEFT JOIN medida m ON ic.CD_MEDIDA = m.Cd_Medida
            LEFT JOIN cardapio c ON ic.CD_CARDAPIO = c.CD_CARDAPIO
            ORDER BY ic.CD_CARDAPIO, ic.TP_REFEICAO, ic.DT_HORA
        """).fetchall()
        cardapios_dict = {}
        for item in cardapios_pac:
            cd = item["CD_CARDAPIO"]
            if cd not in cardapios_dict:
                cardapios_dict[cd] = {"nome": item["DS_CARDAPIO"], "refeicoes": {}}
            tp = str(item["TP_REFEICAO"]) if item["TP_REFEICAO"] else "0"
            nome = NOMES_REFEICAO.get(tp, f"Refeição {tp}")
            if nome not in cardapios_dict[cd]["refeicoes"]:
                cardapios_dict[cd]["refeicoes"][nome] = []
            cardapios_dict[cd]["refeicoes"][nome].append(item)
        cardapios_list = db.execute("SELECT CD_CARDAPIO, DS_CARDAPIO FROM cardapio ORDER BY DS_CARDAPIO").fetchall()
        context.update(cardapios_dict=cardapios_dict, cardapios_list=cardapios_list)

    elif secao == "recomendacao":
        rec = db.execute("""
            SELECT * FROM recomendacao_nutricional
            WHERE CD_PACIENTE = ?
        """, (cd_paciente,)).fetchone()
        dri = db.execute("SELECT * FROM dri_2002 LIMIT 1").fetchone()
        context.update(rec_nutri=rec, dri=dri)

    elif secao == "conduta":
        condutas = db.execute("""
            SELECT * FROM conduta_nutricional
            WHERE CD_PACIENTE = ? ORDER BY NR_PROTOCOLO DESC
        """, (cd_paciente,)).fetchall()
        rec_nutri_list = db.execute("""
            SELECT * FROM rec_nutri ORDER BY NM_REC_NUTRI
        """).fetchall()
        context.update(condutas=condutas, rec_nutri_list=rec_nutri_list)

    elif secao == "relatorio":
        antropometrias = db.execute("""
            SELECT a.*, pp.Dt_Atendimento
            FROM antropometria a
            LEFT JOIN protocolo_paciente pp
                ON a.Cd_Paciente = pp.Cd_Paciente AND a.Nr_Protocolo = pp.Nr_Protocolo
            WHERE a.Cd_Paciente = ? ORDER BY a.Nr_Protocolo ASC
        """, (cd_paciente,)).fetchall()
        context.update(antropometrias=antropometrias,
                       peso_saudavel=peso_saudavel,
                       pct_alteracao_peso=pct_alteracao_peso)

    return render_template("paciente.html", **context)


# --- CADASTROS ---

@app.route("/cadastros")
def cadastros():
    return render_template("cadastros.html")


@app.route("/cadastros/alimentos")
def cadastros_alimentos():
    db = get_db()
    busca = request.args.get("q", "").strip()
    grupo = request.args.get("grupo", "")
    page = int(request.args.get("page", 1))
    per_page = 50
    grupos = db.execute("SELECT CD_GRUPO, DS_GRUPO FROM grupo_alimentos ORDER BY DS_GRUPO").fetchall()
    base_from = """
        FROM alimento a
        LEFT JOIN alimento_grupo ag ON a.cd_alimento = ag.CD_ALIMENTO
        LEFT JOIN grupo_alimentos g ON ag.CD_GRUPO = g.CD_GRUPO
    """
    params = []
    conditions = []
    if busca:
        conditions.append("a.Nm_Alimento LIKE ?")
        params.append(f"%{busca}%")
    if grupo:
        conditions.append("ag.CD_GRUPO = ?")
        params.append(grupo)
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    total = db.execute(f"SELECT COUNT(*) {base_from} {where}", params).fetchone()[0]
    rows = db.execute(f"""
        SELECT a.cd_alimento, a.Nm_Alimento, a.Vl_Carb, a.Vl_Prot, a.Vl_G_Tot,
               a.Vl_Fibra, a.Ds_Fonte, g.DS_GRUPO
        {base_from} {where} ORDER BY a.Nm_Alimento LIMIT ? OFFSET ?
    """, params + [per_page, (page - 1) * per_page]).fetchall()
    total_pages = max(1, (total + per_page - 1) // per_page)
    return render_template("cadastros_alimentos.html", alimentos=rows, grupos=grupos,
        busca=busca, grupo=grupo, page=page, total_pages=total_pages, total=total)


@app.route("/cadastros/alimento/<int:cd_alimento>")
def cadastros_alimento_detalhe(cd_alimento):
    db = get_db()
    alim = db.execute("SELECT * FROM alimento WHERE cd_alimento = ?", (cd_alimento,)).fetchone()
    if not alim:
        return "Alimento não encontrado", 404
    medidas = db.execute("""
        SELECT am.Vl_alimento, m.Ds_Medida
        FROM alimento_medida am
        JOIN medida m ON am.Cd_Medida = m.Cd_Medida
        WHERE am.Cd_Alimento = ?
    """, (cd_alimento,)).fetchall()
    return render_template("cadastros_alimento_detalhe.html", alim=alim, medidas=medidas)


@app.route("/cadastros/receitas")
def cadastros_receitas():
    db = get_db()
    busca = request.args.get("q", "").strip()
    where = "WHERE r.DS_RECEITA LIKE ?" if busca else ""
    params = [f"%{busca}%"] if busca else []
    rows = db.execute(f"""
        SELECT r.CD_RECEITA, r.DS_RECEITA, r.TX_REND, g.DS_GRUPO
        FROM receita r
        LEFT JOIN grupo_receitas g ON r.CD_GRUPO = g.CD_GRUPO
        {where} ORDER BY r.DS_RECEITA
    """, params).fetchall()
    return render_template("cadastros_receitas.html", receitas=rows, busca=busca)


@app.route("/cadastros/receita/<int:cd_receita>")
def cadastros_receita_detalhe(cd_receita):
    db = get_db()
    rec = db.execute("""
        SELECT r.*, g.DS_GRUPO FROM receita r
        LEFT JOIN grupo_receitas g ON r.CD_GRUPO = g.CD_GRUPO
        WHERE r.CD_RECEITA = ?
    """, (cd_receita,)).fetchone()
    if not rec:
        return "Receita não encontrada", 404
    itens = db.execute("""
        SELECT ir.NR_QTD, ir.VL_PTN, ir.VL_CH, ir.VL_LIP,
               a.Nm_Alimento, m.Ds_Medida
        FROM itens_receita ir
        JOIN alimento a ON ir.CD_ALIMENTO = a.cd_alimento
        LEFT JOIN medida m ON ir.CD_MEDIDA = m.Cd_Medida
        WHERE ir.CD_RECEITA = ?
    """, (cd_receita,)).fetchall()
    return render_template("cadastros_receita_detalhe.html", rec=rec, itens=itens)


@app.route("/cadastros/cardapios")
def cadastros_cardapios():
    db = get_db()
    rows = db.execute("SELECT CD_CARDAPIO, DS_CARDAPIO FROM cardapio ORDER BY DS_CARDAPIO").fetchall()
    return render_template("cadastros_cardapios.html", cardapios=rows)


@app.route("/cadastros/cardapio/<int:cd_cardapio>")
def cadastros_cardapio_detalhe(cd_cardapio):
    db = get_db()
    card = db.execute("SELECT * FROM cardapio WHERE CD_CARDAPIO = ?", (cd_cardapio,)).fetchone()
    if not card:
        return "Cardápio não encontrado", 404
    itens = db.execute("""
        SELECT ic.TP_REFEICAO, ic.DT_HORA, ic.QT_ITEM,
               ic.VL_PTN, ic.VL_CH, ic.VL_LIP,
               a.Nm_Alimento, m.Ds_Medida
        FROM itens_cardapio ic
        JOIN alimento a ON ic.CD_ALIMENTO = a.cd_alimento
        LEFT JOIN medida m ON ic.CD_MEDIDA = m.Cd_Medida
        WHERE ic.CD_CARDAPIO = ?
        ORDER BY ic.TP_REFEICAO, ic.DT_HORA
    """, (cd_cardapio,)).fetchall()
    refeicoes = {}
    for item in itens:
        tp = str(item["TP_REFEICAO"]) if item["TP_REFEICAO"] else "0"
        nome = NOMES_REFEICAO.get(tp, f"Refeição {tp}")
        if nome not in refeicoes:
            refeicoes[nome] = []
        refeicoes[nome].append(item)
    return render_template("cadastros_cardapio_detalhe.html", card=card, refeicoes=refeicoes)


@app.route("/cadastros/medidas")
def cadastros_medidas():
    db = get_db()
    rows = db.execute("SELECT * FROM medida ORDER BY Ds_Medida").fetchall()
    return render_template("cadastros_medidas.html", medidas=rows)


@app.route("/cadastros/exames")
def cadastros_exames():
    db = get_db()
    grupos = db.execute("SELECT * FROM grupo_exame ORDER BY CD_GRUPO").fetchall()
    exames = db.execute("""
        SELECT e.*, g.NM_GRUPO
        FROM exame_bioquimico e
        LEFT JOIN grupo_exame g ON e.CD_GRUPO_EXAME = g.CD_GRUPO
        ORDER BY e.CD_GRUPO_EXAME, e.NM_EXAME
    """).fetchall()
    return render_template("cadastros_exames.html", grupos=grupos, exames=exames)


@app.route("/api/stats")
def api_stats():
    db = get_db()
    stats = {}
    for table in ["paciente", "alimento", "receita", "cardapio", "antropometria"]:
        stats[table] = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return jsonify(stats)


# --- MÓDULO ACOMPANHAMENTO ---

ESTADOS_BR = [
    "AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG",
    "PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"
]


@app.route("/acompanhamento")
def acompanhamento_dashboard():
    db = get_db()
    total_ativos = db.execute("SELECT COUNT(*) FROM acompanhamento WHERE status='ativo'").fetchone()[0]
    total_vencidos = db.execute("SELECT COUNT(*) FROM acompanhamento WHERE status='vencido'").fetchone()[0]
    total_pausados = db.execute("SELECT COUNT(*) FROM acompanhamento WHERE status='pausado'").fetchone()[0]
    total_inativos = db.execute("SELECT COUNT(*) FROM acompanhamento WHERE status='inativo'").fetchone()[0]
    total_clientes = total_ativos + total_vencidos + total_pausados + total_inativos

    receita_ativos = db.execute("""
        SELECT COALESCE(SUM(p.valor), 0) FROM acompanhamento a
        JOIN plano p ON a.plano_id = p.id WHERE a.status='ativo'
    """).fetchone()[0]
    receita_total = db.execute("""
        SELECT COALESCE(SUM(p.valor), 0) FROM acompanhamento a
        JOIN plano p ON a.plano_id = p.id
    """).fetchone()[0]
    ticket_medio = receita_total / total_clientes if total_clientes > 0 else 0

    dist_plano = db.execute("""
        SELECT p.nome, COUNT(*) as qt, p.valor
        FROM acompanhamento a
        JOIN plano p ON a.plano_id = p.id
        WHERE a.status IN ('ativo','pausado')
        GROUP BY p.id ORDER BY qt DESC
    """).fetchall()

    dist_estado = db.execute("""
        SELECT estado, COUNT(*) as qt FROM acompanhamento
        WHERE estado IS NOT NULL AND estado != ''
        GROUP BY estado ORDER BY qt DESC
    """).fetchall()

    hoje = datetime.now()
    aniversariantes = db.execute("""
        SELECT nome, dt_nascimento, status FROM acompanhamento
        WHERE dt_nascimento IS NOT NULL AND dt_nascimento != ''
        ORDER BY nome
    """).fetchall()
    aniv_proximos = []
    for a in aniversariantes:
        try:
            dt = datetime.fromisoformat(str(a["dt_nascimento"]))
            aniv_este_ano = dt.replace(year=hoje.year)
            if aniv_este_ano < hoje:
                aniv_este_ano = dt.replace(year=hoje.year + 1)
            dias = (aniv_este_ano - hoje).days
            if 0 <= dias <= 30:
                aniv_proximos.append({"nome": a["nome"], "data": dt.strftime("%d/%m"), "dias": dias})
        except Exception:
            pass

    planos_cadastrados = db.execute("SELECT COUNT(*) FROM plano WHERE ativo=1").fetchone()[0]

    return render_template("acompanhamento_dashboard.html",
        total_ativos=total_ativos, total_vencidos=total_vencidos,
        total_pausados=total_pausados, total_inativos=total_inativos,
        receita_ativos=receita_ativos, receita_total=receita_total,
        ticket_medio=ticket_medio, dist_plano=dist_plano,
        dist_estado=dist_estado, aniv_proximos=aniv_proximos,
        planos_cadastrados=planos_cadastrados)


@app.route("/acompanhamento/clientes")
def acompanhamento_clientes():
    db = get_db()
    busca = request.args.get("q", "").strip()
    filtro_plano = request.args.get("plano", "")
    filtro_status = request.args.get("status", "")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))

    conditions = []
    params = []
    if busca:
        conditions.append("(a.nome LIKE ? OR a.apelido LIKE ? OR a.documento LIKE ?)")
        params.extend([f"%{busca}%"] * 3)
    if filtro_plano:
        conditions.append("a.plano_id = ?")
        params.append(filtro_plano)
    if filtro_status:
        conditions.append("a.status = ?")
        params.append(filtro_status)

    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    total = db.execute(f"SELECT COUNT(*) FROM acompanhamento a {where}", params).fetchone()[0]
    rows = db.execute(f"""
        SELECT a.*, p.nome AS plano_nome, p.valor AS plano_valor
        FROM acompanhamento a
        LEFT JOIN plano p ON a.plano_id = p.id
        {where} ORDER BY a.nome LIMIT ? OFFSET ?
    """, params + [per_page, (page - 1) * per_page]).fetchall()
    total_pages = max(1, (total + per_page - 1) // per_page)
    planos = db.execute("SELECT id, nome FROM plano WHERE ativo=1 ORDER BY nome").fetchall()
    return render_template("acompanhamento_clientes.html", clientes=rows,
        busca=busca, filtro_plano=filtro_plano, filtro_status=filtro_status,
        page=page, per_page=per_page, total_pages=total_pages, total=total,
        planos=planos, calc_idade_detalhada=calc_idade_detalhada)


@app.route("/acompanhamento/clientes/novo", methods=["GET", "POST"])
def acompanhamento_cliente_novo():
    db = get_db()
    if request.method == "POST":
        db.execute("""
            INSERT INTO acompanhamento (nome, apelido, whatsapp, documento, email,
                dt_nascimento, estado, cidade, plano_id, dt_inicio, status,
                status_plano, possui_vencimento, alerta_atendimentos, etiqueta)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            request.form.get("nome"), request.form.get("apelido"),
            request.form.get("whatsapp"), request.form.get("documento"),
            request.form.get("email"), request.form.get("dt_nascimento"),
            request.form.get("estado"), request.form.get("cidade"),
            request.form.get("plano_id") or None, request.form.get("dt_inicio"),
            "ativo", "ativo",
            1 if request.form.get("possui_vencimento") == "sim" else 0,
            request.form.get("alerta_atendimentos", "nao_notificar"),
            request.form.get("etiqueta"),
        ))
        db.commit()
        return redirect("/acompanhamento/clientes")
    planos = db.execute("SELECT * FROM plano WHERE ativo=1 ORDER BY nome").fetchall()
    return render_template("acompanhamento_cliente_form.html",
        cliente=None, planos=planos, estados=ESTADOS_BR)


@app.route("/acompanhamento/clientes/<int:cid>/editar", methods=["GET", "POST"])
def acompanhamento_cliente_editar(cid):
    db = get_db()
    cliente = db.execute("SELECT * FROM acompanhamento WHERE id=?", (cid,)).fetchone()
    if not cliente:
        return "Cliente não encontrado", 404
    if request.method == "POST":
        db.execute("""
            UPDATE acompanhamento SET nome=?, apelido=?, whatsapp=?, documento=?,
                email=?, dt_nascimento=?, estado=?, cidade=?, plano_id=?,
                dt_inicio=?, status=?, status_plano=?, possui_vencimento=?,
                alerta_atendimentos=?, etiqueta=?
            WHERE id=?
        """, (
            request.form.get("nome"), request.form.get("apelido"),
            request.form.get("whatsapp"), request.form.get("documento"),
            request.form.get("email"), request.form.get("dt_nascimento"),
            request.form.get("estado"), request.form.get("cidade"),
            request.form.get("plano_id") or None, request.form.get("dt_inicio"),
            request.form.get("status", "ativo"),
            request.form.get("status_plano", "ativo"),
            1 if request.form.get("possui_vencimento") == "sim" else 0,
            request.form.get("alerta_atendimentos", "nao_notificar"),
            request.form.get("etiqueta"), cid,
        ))
        db.commit()
        return redirect("/acompanhamento/clientes")
    planos = db.execute("SELECT * FROM plano WHERE ativo=1 ORDER BY nome").fetchall()
    return render_template("acompanhamento_cliente_form.html",
        cliente=cliente, planos=planos, estados=ESTADOS_BR)


@app.route("/acompanhamento/clientes/<int:cid>/excluir", methods=["POST"])
def acompanhamento_cliente_excluir(cid):
    db = get_db()
    db.execute("DELETE FROM acompanhamento WHERE id=?", (cid,))
    db.commit()
    return redirect("/acompanhamento/clientes")


@app.route("/acompanhamento/planos")
def acompanhamento_planos():
    db = get_db()
    planos = db.execute("""
        SELECT p.*, (SELECT COUNT(*) FROM acompanhamento a WHERE a.plano_id = p.id) AS qt_clientes
        FROM plano p ORDER BY p.nome
    """).fetchall()
    return render_template("acompanhamento_planos.html", planos=planos)


@app.route("/acompanhamento/planos/novo", methods=["GET", "POST"])
def acompanhamento_plano_novo():
    if request.method == "POST":
        db = get_db()
        db.execute("INSERT INTO plano (nome, num_consultas, valor, descricao) VALUES (?,?,?,?)", (
            request.form.get("nome"),
            int(request.form.get("num_consultas", 1)),
            float(request.form.get("valor", "0").replace(",", ".")),
            request.form.get("descricao"),
        ))
        db.commit()
        return redirect("/acompanhamento/planos")
    return render_template("acompanhamento_plano_form.html", plano=None)


@app.route("/acompanhamento/planos/<int:pid>/editar", methods=["GET", "POST"])
def acompanhamento_plano_editar(pid):
    db = get_db()
    plano = db.execute("SELECT * FROM plano WHERE id=?", (pid,)).fetchone()
    if not plano:
        return "Plano não encontrado", 404
    if request.method == "POST":
        db.execute("UPDATE plano SET nome=?, num_consultas=?, valor=?, descricao=?, ativo=? WHERE id=?", (
            request.form.get("nome"),
            int(request.form.get("num_consultas", 1)),
            float(request.form.get("valor", "0").replace(",", ".")),
            request.form.get("descricao"),
            1 if request.form.get("ativo") == "1" else 0, pid,
        ))
        db.commit()
        return redirect("/acompanhamento/planos")
    return render_template("acompanhamento_plano_form.html", plano=plano)


@app.route("/acompanhamento/planos/<int:pid>/excluir", methods=["POST"])
def acompanhamento_plano_excluir(pid):
    db = get_db()
    db.execute("DELETE FROM plano WHERE id=?", (pid,))
    db.commit()
    return redirect("/acompanhamento/planos")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
