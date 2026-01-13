import re
import pandas as pd
import dash
from dash import html, dcc, Input, Output, dash_table
import plotly.express as px
from conexion_mysql import crear_conexion

# ======================================================
# === OBL DIGITAL DASHBOARD — GENERAL LTV (Dark Gold) ===
# ======================================================

# ------------------------------------------------------
# 🔹 CARGA DE DATOS (FTD + RTN)
# ------------------------------------------------------
def cargar_datos():
    try:
        conexion = crear_conexion()

        df_ftd = pd.read_sql(
            "SELECT date, country, affiliate, source, usd_total FROM FTD_MASTER_CLEAN",
            conexion
        )

        df_rtn = pd.read_sql(
            "SELECT date, country, affiliate, source, usd_total FROM RTN_MASTER_CLEAN",
            conexion
        )

        conexion.close()
        return df_ftd, df_rtn

    except Exception as e:
        print(f"⚠️ Error SQL: {e}")
        return pd.DataFrame(), pd.DataFrame()


# ------------------------------------------------------
# 🔹 LIMPIEZA USD
# ------------------------------------------------------
def limpiar_usd(valor):
    if pd.isna(valor):
        return 0.0
    s = re.sub(r"[^\d,.\-]", "", str(valor))
    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except:
        return 0.0


# ------------------------------------------------------
# 🔹 CARGA Y NORMALIZACIÓN
# ------------------------------------------------------
df_ftd, df_rtn = cargar_datos()

for df_x in [df_ftd, df_rtn]:
    df_x.columns = [c.lower().strip() for c in df_x.columns]
    df_x["date"] = pd.to_datetime(df_x["date"], errors="coerce").dt.tz_localize(None)
    df_x = df_x[df_x["date"].notna()]
    df_x["usd_total"] = df_x["usd_total"].apply(limpiar_usd)

    for col in ["country", "affiliate", "source"]:
        df_x[col] = df_x[col].astype(str).str.strip().str.title()
        df_x[col].replace({"Nan": None, "None": None, "": None}, inplace=True)

fecha_min = min(df_ftd["date"].min(), df_rtn["date"].min())
fecha_max = max(df_ftd["date"].max(), df_rtn["date"].max())


# ------------------------------------------------------
# 🔹 FORMATO
# ------------------------------------------------------
def formato_km(valor):
    try:
        return f"{valor:,.2f}"
    except:
        return "0.00"


# ------------------------------------------------------
# 🔹 DASH APP
# ------------------------------------------------------
external_scripts = [
    "https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js",
]

app = dash.Dash(__name__, external_scripts=external_scripts)
server = app.server
app.title = "OBL Digital — GENERAL LTV Dashboard"


# ------------------------------------------------------
# 🔹 LAYOUT
# ------------------------------------------------------
app.layout = html.Div(
    style={"backgroundColor": "#0d0d0d", "padding": "20px"},
    children=[

        html.H1("📊 DASHBOARD GENERAL LTV", style={
            "textAlign": "center",
            "color": "#D4AF37",
            "marginBottom": "30px",
            "fontWeight": "bold"
        }),

        html.Div(style={"display": "flex", "justifyContent": "space-between"}, children=[

            # ================== FILTROS ==================
            html.Div(style={
                "width": "25%",
                "backgroundColor": "#1a1a1a",
                "padding": "20px",
                "borderRadius": "12px",
                "boxShadow": "0 0 15px rgba(212,175,55,0.3)",
                "textAlign": "center",
            }, children=[
                html.H4("Date", style={"color": "#D4AF37"}),
                dcc.DatePickerRange(
                    id="filtro-fecha",
                    start_date=fecha_min,
                    end_date=fecha_max,
                    display_format="YYYY-MM-DD",
                ),
                html.H4("Affiliate", style={"color": "#D4AF37", "marginTop": "10px"}),
                dcc.Dropdown(
                    sorted(df_ftd["affiliate"].dropna().unique()),
                    multi=True,
                    id="filtro-affiliate"
                ),
                html.H4("Source", style={"color": "#D4AF37", "marginTop": "10px"}),
                dcc.Dropdown(
                    sorted(df_ftd["source"].dropna().unique()),
                    multi=True,
                    id="filtro-source"
                ),
                html.H4("Country", style={"color": "#D4AF37", "marginTop": "10px"}),
                dcc.Dropdown(
                    sorted(df_ftd["country"].dropna().unique()),
                    multi=True,
                    id="filtro-country"
                ),
            ]),

            # ================== PANEL ==================
            html.Div(style={"width": "72%"}, children=[

                html.Div(style={"display": "flex", "justifyContent": "space-around"}, children=[
                    html.Div(id="indicador-ftds", style={"width": "30%"}),
                    html.Div(id="indicador-amount", style={"width": "30%"}),
                    html.Div(id="indicador-ltv", style={"width": "30%"}),
                ]),

                html.Br(),

                html.Div(style={"display": "flex", "flexWrap": "wrap", "gap": "20px"}, children=[
                    dcc.Graph(id="grafico-ltv-affiliate", style={"width": "48%", "height": "340px"}),
                    dcc.Graph(id="grafico-ltv-country", style={"width": "48%", "height": "340px"}),
                    dcc.Graph(id="grafico-bar-country-aff", style={"width": "100%", "height": "360px"}),
                ]),

                html.Br(),

                html.H4("📋 Detalle General LTV", style={"color": "#D4AF37"}),

                dash_table.DataTable(
                    id="tabla-detalle",
                    columns=[
                        {"name": "DATE", "id": "date"},
                        {"name": "COUNTRY", "id": "country"},
                        {"name": "AFFILIATE", "id": "affiliate"},
                        {"name": "SOURCE", "id": "source"},
                        {"name": "TOTAL AMOUNT", "id": "usd_total"},
                        {"name": "FTD'S", "id": "count_ftd"},
                        {"name": "GENERAL LTV", "id": "general_ltv"},
                    ],
                    page_size=15,
                    style_cell={"textAlign": "center", "color": "#f2f2f2", "backgroundColor": "#1a1a1a"},
                    style_header={"backgroundColor": "#D4AF37", "color": "#000", "fontWeight": "bold"},
                ),
            ])
        ])
    ]
)


# ------------------------------------------------------
# 🔹 CALLBACK
# ------------------------------------------------------
@app.callback(
    [
        Output("indicador-ftds", "children"),
        Output("indicador-amount", "children"),
        Output("indicador-ltv", "children"),
        Output("grafico-ltv-affiliate", "figure"),
        Output("grafico-ltv-country", "figure"),
        Output("grafico-bar-country-aff", "figure"),
        Output("tabla-detalle", "data"),
    ],
    [
        Input("filtro-fecha", "start_date"),
        Input("filtro-fecha", "end_date"),
        Input("filtro-affiliate", "value"),
        Input("filtro-source", "value"),
        Input("filtro-country", "value"),
    ],
)
def actualizar_dashboard(start, end, affiliates, sources, countries):

    ftd = df_ftd.copy()
    rtn = df_rtn.copy()

    if start and end:
        start, end = pd.to_datetime(start), pd.to_datetime(end)
        ftd = ftd[(ftd["date"] >= start) & (ftd["date"] <= end)]
        rtn = rtn[(rtn["date"] >= start) & (rtn["date"] <= end)]

    for col, vals in {
        "affiliate": affiliates,
        "source": sources,
        "country": countries
    }.items():
        if vals:
            ftd = ftd[ftd[col].isin(vals)]
            rtn = rtn[rtn[col].isin(vals)]

    # ================== GENERAL LTV MENSUAL ==================
    ftd["month"] = ftd["date"].dt.to_period("M")
    rtn["month"] = rtn["date"].dt.to_period("M")

    ftd_m = ftd.groupby(
        ["month", "country", "affiliate", "source"], as_index=False
    ).agg(
        usd_ftd=("usd_total", "sum"),
        count_ftd=("usd_total", "count")
    )

    rtn_m = rtn.groupby(
        ["month", "country", "affiliate", "source"], as_index=False
    ).agg(
        usd_rtn=("usd_total", "sum")
    )

    df_ltv = pd.merge(
        ftd_m, rtn_m,
        on=["month", "country", "affiliate", "source"],
        how="left"
    )

    df_ltv["usd_rtn"] = df_ltv["usd_rtn"].fillna(0)
    df_ltv["usd_total"] = df_ltv["usd_ftd"] + df_ltv["usd_rtn"]
    df_ltv["general_ltv"] = df_ltv["usd_total"] / df_ltv["count_ftd"]

    df_ltv["date"] = df_ltv["month"].dt.to_timestamp("M")
    df_ltv.drop(columns=["month"], inplace=True)

    # ================== KPIs ==================
    total_amount = df_ltv["usd_total"].sum()
    total_ftds = df_ltv["count_ftd"].sum()
    general_ltv_total = total_amount / total_ftds if total_ftds > 0 else 0

    card_style = {
        "backgroundColor": "#1a1a1a",
        "borderRadius": "10px",
        "padding": "20px",
        "width": "80%",
        "textAlign": "center",
        "boxShadow": "0 0 10px rgba(212,175,55,0.3)",
    }

    indicador_ftds = html.Div([
        html.H4("FTD'S", style={"color": "#D4AF37"}),
        html.H2(f"{int(total_ftds):,}", style={"color": "#FFF"})
    ], style=card_style)

    indicador_amount = html.Div([
        html.H4("TOTAL AMOUNT", style={"color": "#D4AF37"}),
        html.H2(f"${formato_km(total_amount)}", style={"color": "#FFF"})
    ], style=card_style)

    indicador_ltv = html.Div([
        html.H4("GENERAL LTV", style={"color": "#D4AF37"}),
        html.H2(f"${general_ltv_total:,.2f}", style={"color": "#FFF"})
    ], style=card_style)

    # ================== GRÁFICAS ==================
    df_aff = df_ltv.groupby("affiliate", as_index=False).agg(
        {"usd_total": "sum", "count_ftd": "sum"}
    )
    df_aff["general_ltv"] = df_aff["usd_total"] / df_aff["count_ftd"]

    fig_aff = px.pie(
        df_aff, names="affiliate", values="general_ltv",
        title="GENERAL LTV by Affiliate",
        color_discrete_sequence=px.colors.sequential.YlOrBr
    )

    df_cty = df_ltv.groupby("country", as_index=False).agg(
        {"usd_total": "sum", "count_ftd": "sum"}
    )
    df_cty["general_ltv"] = df_cty["usd_total"] / df_cty["count_ftd"]

    fig_cty = px.pie(
        df_cty, names="country", values="general_ltv",
        title="GENERAL LTV by Country",
        color_discrete_sequence=px.colors.sequential.YlOrBr
    )

    fig_bar = px.bar(
        df_ltv,
        x="country",
        y="general_ltv",
        color="affiliate",
        barmode="group",
        title="GENERAL LTV by Country and Affiliate",
        color_discrete_sequence=px.colors.sequential.YlOrBr
    )

    for fig in [fig_aff, fig_cty, fig_bar]:
        fig.update_layout(
            paper_bgcolor="#0d0d0d",
            plot_bgcolor="#0d0d0d",
            font_color="#f2f2f2",
            title_font_color="#D4AF37"
        )

    tabla = df_ltv.copy()
    tabla["date"] = tabla["date"].dt.strftime("%Y-%m-%d")

    return (
        indicador_ftds,
        indicador_amount,
        indicador_ltv,
        fig_aff,
        fig_cty,
        fig_bar,
        tabla.round(2).to_dict("records")
    )

# === 9️⃣ Captura PDF/PPT desde iframe ===
app.index_string = '''
<!DOCTYPE html>
<html>
<head>
  {%metas%}
  <title>OBL Digital — Dashboard FTD</title>
  {%favicon%}
  {%css%}
  <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
</head>
<body>
  {%app_entry%}
  <footer>
    {%config%}
    {%scripts%}
    {%renderer%}
  </footer>

  <script>
    window.addEventListener("message", async (event) => {
      if (!event.data || event.data.action !== "capture_dashboard") return;

      try {
        const canvas = await html2canvas(document.body, { useCORS: true, scale: 2, backgroundColor: "#0d0d0d" });
        const imgData = canvas.toDataURL("image/png");

        window.parent.postMessage({
          action: "capture_image",
          img: imgData,
          filetype: event.data.type
        }, "*");
      } catch (err) {
        console.error("Error al capturar dashboard:", err);
        window.parent.postMessage({ action: "capture_done" }, "*");
      }
    });
  </script>
</body>
</html>
'''



if __name__ == "__main__":
    app.run_server(debug=True, port=8053)



