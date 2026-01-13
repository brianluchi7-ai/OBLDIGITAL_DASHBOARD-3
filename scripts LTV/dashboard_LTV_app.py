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
# 🔹 CARGA DE DATOS DESDE FTD + RTN
# ------------------------------------------------------
def cargar_datos():
    try:
        conexion = crear_conexion()
        print("✅ Conectado a Railway MySQL")

        df_ftd = pd.read_sql("SELECT * FROM FTD_MASTER_CLEAN", conexion)
        df_rtn = pd.read_sql("SELECT * FROM RTN_MASTER_CLEAN", conexion)

        conexion.close()

        df_ftd["deposit_type"] = "Ftd"
        df_rtn["deposit_type"] = "Rtn"

        df = pd.concat([df_ftd, df_rtn], ignore_index=True)
        return df

    except Exception as e:
        print(f"⚠️ Error SQL: {e}")
        return pd.DataFrame()


# === 1️⃣ Cargar datos ===
df = cargar_datos()
df.columns = [c.strip().lower() for c in df.columns]

# === 2️⃣ Normalizar columnas esperadas ===
if "source" not in df.columns:
    df["source"] = None

if "usd_total" not in df.columns:
    for alt in ["usd", "total_amount", "amount_usd", "deposit_usd"]:
        if alt in df.columns:
            df.rename(columns={alt: "usd_total"}, inplace=True)
            break

# === 3️⃣ Normalizar fechas ===
def convertir_fecha(valor):
    try:
        s = str(valor).strip()
        if "/" in s:
            return pd.to_datetime(s, format="%d/%m/%Y", errors="coerce")
        return pd.to_datetime(s.split(" ")[0], errors="coerce")
    except:
        return pd.NaT

df["date"] = df["date"].astype(str).apply(convertir_fecha)
df = df[df["date"].notna()]
df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)

# === 4️⃣ Limpieza de montos ===
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

df["usd_total"] = df["usd_total"].apply(limpiar_usd)

# === 5️⃣ Limpieza de texto ===
for col in ["country", "affiliate", "source", "deposit_type"]:
    if col in df.columns:
        df[col] = df[col].astype(str).str.strip().str.title()
        df[col].replace({"Nan": None, "None": None, "": None}, inplace=True)

# === 6️⃣ Rango de fechas ===
fecha_min, fecha_max = df["date"].min(), df["date"].max()

# === 7️⃣ Formato ===
def formato_km(valor):
    try:
        return f"{valor:,.2f}"
    except:
        return "0.00"


# === 8️⃣ Inicializar app ===
app = dash.Dash(__name__)
server = app.server
app.title = "OBL Digital — GENERAL LTV Dashboard"


# === 9️⃣ Layout (SIN CAMBIOS) ===
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

            html.Div(style={
                "width": "25%",
                "backgroundColor": "#1a1a1a",
                "padding": "20px",
                "borderRadius": "12px",
                "boxShadow": "0 0 15px rgba(212,175,55,0.3)",
                "textAlign": "center",
            }, children=[
                dcc.DatePickerRange(
                    id="filtro-fecha",
                    start_date=fecha_min,
                    end_date=fecha_max,
                    display_format="YYYY-MM-DD",
                ),
                dcc.Dropdown(sorted(df["affiliate"].dropna().unique()), multi=True, id="filtro-affiliate"),
                dcc.Dropdown(sorted(df["source"].dropna().unique()), multi=True, id="filtro-source"),
                dcc.Dropdown(sorted(df["country"].dropna().unique()), multi=True, id="filtro-country"),
            ]),

            html.Div(style={"width": "72%"}, children=[
                html.Div(style={"display": "flex", "justifyContent": "space-around"}, children=[
                    html.Div(id="indicador-ftds", style={"width": "30%"}),
                    html.Div(id="indicador-amount", style={"width": "30%"}),
                    html.Div(id="indicador-ltv", style={"width": "30%"}),
                ]),
                html.Br(),
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
                ),
            ])
        ])
    ]
)


# === 🔟 CALLBACK (SIN CAMBIOS) ===
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

    df_filtrado = df.copy()

    if start and end:
        df_filtrado = df_filtrado[
            (df_filtrado["date"] >= pd.to_datetime(start)) &
            (df_filtrado["date"] <= pd.to_datetime(end))
        ]
    if affiliates:
        df_filtrado = df_filtrado[df_filtrado["affiliate"].isin(affiliates)]
    if sources:
        df_filtrado = df_filtrado[df_filtrado["source"].isin(sources)]
    if countries:
        df_filtrado = df_filtrado[df_filtrado["country"].isin(countries)]

    df_filtrado["month"] = df_filtrado["date"].dt.to_period("M")

    df_month = (
        df_filtrado
        .groupby(["month", "country", "affiliate", "source"], as_index=False)
        .apply(lambda x: pd.Series({
            "usd_total": x["usd_total"].sum(),
            "count_ftd": (x["deposit_type"] == "Ftd").sum()
        }))
        .reset_index(drop=True)
    )

    df_month["general_ltv"] = df_month.apply(
        lambda r: r["usd_total"] / r["count_ftd"] if r["count_ftd"] > 0 else 0,
        axis=1
    )

    df_month["date"] = df_month["month"].dt.to_timestamp("M")
    df_month.drop(columns=["month"], inplace=True)

    total_amount = df_month["usd_total"].sum()
    total_ftds = df_month["count_ftd"].sum()
    general_ltv_total = total_amount / total_ftds if total_ftds > 0 else 0

    indicador_ftds = f"FTD'S: {int(total_ftds):,}"
    indicador_amount = f"TOTAL AMOUNT: ${formato_km(total_amount)}"
    indicador_ltv = f"GENERAL LTV: ${general_ltv_total:,.2f}"

    fig_aff = px.pie(df_month.groupby("affiliate", as_index=False).sum(),
                     names="affiliate", values="general_ltv")

    fig_cty = px.pie(df_month.groupby("country", as_index=False).sum(),
                     names="country", values="general_ltv")

    fig_bar = px.bar(df_month, x="country", y="general_ltv",
                     color="affiliate", barmode="group")

    tabla = df_month.copy()
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









