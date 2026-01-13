import re
import pandas as pd
import dash
from dash import html, dcc, Input, Output, dash_table
import plotly.express as px
from conexion_mysql import crear_conexion

# ======================================================
# 🔹 UTILIDADES
# ======================================================
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


def normalizar_columnas(df):
    df.columns = [c.lower().strip() for c in df.columns]

    if "date" not in df.columns:
        for alt in ["created_at", "deposit_date", "fecha", "day"]:
            if alt in df.columns:
                df.rename(columns={alt: "date"}, inplace=True)
                break

    if "usd_total" not in df.columns:
        for alt in ["usd", "amount", "amount_usd", "total_usd", "deposit_usd"]:
            if alt in df.columns:
                df.rename(columns={alt: "usd_total"}, inplace=True)
                break

    return df


# ======================================================
# 🔹 CARGA DE DATOS
# ======================================================
def cargar_datos():
    conexion = crear_conexion()

    df_ftd = pd.read_sql("SELECT * FROM FTD_MASTER_CLEAN", conexion)
    df_rtn = pd.read_sql("SELECT * FROM RTN_MASTER_CLEAN", conexion)

    conexion.close()
    print("✅ Datos cargados correctamente")

    return df_ftd, df_rtn


df_ftd, df_rtn = cargar_datos()

df_ftd = normalizar_columnas(df_ftd)
df_rtn = normalizar_columnas(df_rtn)

for df_x in [df_ftd, df_rtn]:
    df_x["date"] = pd.to_datetime(df_x["date"], errors="coerce")
    df_x.dropna(subset=["date"], inplace=True)
    df_x["date"] = df_x["date"].dt.tz_localize(None)

    df_x["usd_total"] = df_x["usd_total"].apply(limpiar_usd)

    for col in ["country", "affiliate", "source"]:
        if col in df_x.columns:
            df_x[col] = df_x[col].astype(str).str.strip().str.title()
            df_x[col].replace({"Nan": None, "None": None, "": None}, inplace=True)


fecha_min = min(df_ftd["date"].min(), df_rtn["date"].min())
fecha_max = max(df_ftd["date"].max(), df_rtn["date"].max())


def formato_km(v):
    return f"{v:,.2f}"


# ======================================================
# 🔹 APP
# ======================================================
app = dash.Dash(__name__)
server = app.server
app.title = "OBL Digital — GENERAL LTV"


# ======================================================
# 🔹 LAYOUT
# ======================================================
app.layout = html.Div(
    style={"backgroundColor": "#0d0d0d", "padding": "20px"},
    children=[

        html.H1("📊 DASHBOARD GENERAL LTV",
                style={"color": "#D4AF37", "textAlign": "center"}),

        html.Div(style={"display": "flex"}, children=[

            # -------- FILTROS --------
            html.Div(style={"width": "25%", "padding": "20px"}, children=[
                dcc.DatePickerRange(
                    id="filtro-fecha",
                    start_date=fecha_min,
                    end_date=fecha_max,
                    display_format="YYYY-MM-DD"
                ),
                dcc.Dropdown(sorted(df_ftd["affiliate"].dropna().unique()),
                             multi=True, id="filtro-affiliate"),
                dcc.Dropdown(sorted(df_ftd["source"].dropna().unique()),
                             multi=True, id="filtro-source"),
                dcc.Dropdown(sorted(df_ftd["country"].dropna().unique()),
                             multi=True, id="filtro-country"),
            ]),

            # -------- PANEL --------
            html.Div(style={"width": "75%"}, children=[

                html.Div(style={"display": "flex", "justifyContent": "space-around"}, children=[
                    html.Div(id="indicador-ftds"),
                    html.Div(id="indicador-amount"),
                    html.Div(id="indicador-ltv"),
                ]),

                dcc.Graph(id="grafico-ltv-affiliate"),
                dcc.Graph(id="grafico-ltv-country"),
                dcc.Graph(id="grafico-bar-country-aff"),

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
                    style_cell={"textAlign": "center"},
                )
            ])
        ])
    ]
)


# ======================================================
# 🔹 CALLBACK
# ======================================================
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
    ]
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

    # ================= KPI REALES =================
    total_ftds = ftd.shape[0]
    total_amount = ftd["usd_total"].sum() + rtn["usd_total"].sum()
    general_ltv_total = total_amount / total_ftds if total_ftds > 0 else 0

    # ================= MENSUAL =================
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
        how="outer"
    )

    df_ltv.fillna(0, inplace=True)
    df_ltv["usd_total"] = df_ltv["usd_ftd"] + df_ltv["usd_rtn"]
    df_ltv["general_ltv"] = df_ltv["usd_total"] / df_ltv["count_ftd"].replace(0, pd.NA)
    df_ltv["general_ltv"] = df_ltv["general_ltv"].fillna(0)

    df_ltv["date"] = df_ltv["month"].dt.to_timestamp("M")

    # ================= GRAFICAS =================
    fig_aff = px.pie(df_ltv.groupby("affiliate", as_index=False).sum(),
                     names="affiliate", values="general_ltv")

    fig_cty = px.pie(df_ltv.groupby("country", as_index=False).sum(),
                     names="country", values="general_ltv")

    fig_bar = px.bar(df_ltv, x="country", y="general_ltv",
                     color="affiliate", barmode="group")

    tabla = df_ltv.copy()
    tabla["date"] = tabla["date"].dt.strftime("%Y-%m-%d")

    return (
        f"FTD'S: {total_ftds:,}",
        f"TOTAL AMOUNT: ${formato_km(total_amount)}",
        f"GENERAL LTV: ${general_ltv_total:,.2f}",
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








