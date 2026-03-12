import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import numpy as np
import os

st.set_page_config(page_title="Gestione Portafoglio Avanzata", layout="wide", page_icon="📈")

# --- 1. FUNZIONI DI SUPPORTO E MAPPING ---
def map_ticker(row):
    """Mappa i codici del CSV a Yahoo Finance"""
    sym = str(row['Simbolo']).strip()
    if pd.isna(sym) or sym == 'nan': return None
    
    overrides = {
        'MGT.MI': 'MGT.PA', 'OR.EQ': 'OR.PA', 'AHLA.EQ': 'AHLA.F', 'LCOP.MI': 'LCOP.L',
        'EMOVE.MI': 'ECAR.L', 'EURO.MI': 'SMEU.DE', 'HSTE.MI': '3033.HK', 'CHINA.MI': 'CC1.PA',
        '1EL.MI': 'EL.PA', '1ITX.MI': 'ITX.MC', 'BRK/B.N': 'BRK-B', 'OXY/WS.N': 'OXY',
        'REMX.MI': 'VVMX.DE', 'DAPP.MI': 'DAPP', '1NVDA.MI': 'NVDA', '1MU.MI': 'MU',
        '1GOOGL.MI': 'GOOGL', '1CALM.MI': 'CALM', '1AVGO.MI': 'AVGO', '1FDS.MI': 'FDS',
        'PHPD.MI': 'PHPD.MI', 'VBTC.FRA': 'VBTC.DE', 'VS0L.FRA': 'VS0L.DE', '2BTC.FRA':'2BTC.DE',
        'WETH.FRA': 'WETH.DE', 'VETH.FRA': 'VETH.DE', 'NOV.FRA':'NOV.F', '4COP.FRA':'4COP.DE',
        'GBSE.MI':'GBSE.MI', 'RACE.MI':'RACE.MI', 'CE.MI':'CE.MI', 'OXY.N': 'OXY', 'TSM.N': 'TSM',
        'RARE.MI': 'RARE.L', 'AAPL.O': 'AAPL', 'WFC.N': 'WFC', 'FLNC.O': 'FLNC', 'SEI.N': 'SEI',
        'CWEN.N': 'CWEN', 'IBM.N': 'IBM', 'DLO.O': 'DLO', 'SNDK.O': 'SNDK', 'BEPC.N': 'BEPC', 'INR.N': 'INR'
    }
    if sym in overrides: return overrides[sym]
    
    if 'CFD' in sym:
        clean = sym.replace('.CFD', '').replace('CFD', '')
        return 'RACE.MI' if clean == 'RACE' else clean
    
    if sym.endswith('.O') or sym.endswith('.N') or sym.endswith('.OQ'): return sym.split('.')[0]
    if sym.endswith('.FRA'): return f"{sym.split('.')[0]}.DE"
    
    return sym

def pulisci_dati(df):
    """Pulisce il CSV ed estrae i valori esatti calcolati dalla Banca"""
    cols = df.columns.tolist()
    new_cols = []
    for c in cols:
        if 'Quantit' in c: new_cols.append('Quantita')
        elif 'P.zo medio di carico' in c: new_cols.append('Prezzo_Carico_CSV')
        elif 'Valore di carico' in c: new_cols.append('Valore_Carico_CSV')
        elif 'P.zo di mercato' in c: new_cols.append('Prezzo_Mercato_CSV')
        elif 'Valore di mercato' in c: new_cols.append('Valore_Mercato_CSV')
        elif 'Var%' in c: new_cols.append('Var_Perc_CSV')
        elif 'Var' in c and 'valuta' not in c and '%' not in c: new_cols.append('Var_EUR_CSV')
        else: new_cols.append(c)
    df.columns = new_cols

    def to_float(val):
        if pd.isna(val): return 0.0
        if isinstance(val, (int, float)): return float(val)
        try: return float(str(val).replace('.', '').replace(',', '.'))
        except: return 0.0

    num_cols = ['Quantita', 'Prezzo_Carico_CSV', 'Valore_Carico_CSV', 'Prezzo_Mercato_CSV', 'Valore_Mercato_CSV', 'Var_EUR_CSV']
    for col in num_cols:
        if col in df.columns:
            df[col] = df[col].apply(to_float)
            
    return df[df['Quantita'] > 0].copy()

# Caching dello storico per evitare i blocchi di Yahoo
@st.cache_data(ttl=3600)
def fetch_historical_data(tickers):
    hist_data = yf.download(tickers, period="5y", group_by='ticker')
    fx_data = yf.download("EUR=X", period="1d")['Close']
    fx_usd = float(fx_data.iloc[-1, 0]) if isinstance(fx_data, pd.DataFrame) else float(fx_data.iloc[-1])
    return hist_data, fx_usd

# --- 2. GESTIONE DELLA MEMORIA (BASELINE) ---
BASELINE_FILE = "baseline_portfolio.csv"

# Sidebar per il caricamento
with st.sidebar:
    st.header("📂 Gestione Dati")
    uploaded_file = st.file_uploader("Carica il Portafoglio (CSV della Banca)", type=['csv'])
    
    if uploaded_file is not None:
        raw_df = pd.read_csv(uploaded_file, sep=';', encoding='latin1')
        df_clean = pulisci_dati(raw_df)
        df_clean['Yahoo_Ticker'] = df_clean.apply(map_ticker, axis=1)
        # Salva la baseline in memoria locale!
        df_clean.to_csv(BASELINE_FILE, index=False)
        st.success("✅ Portafoglio memorizzato con successo come nuova Base!")

# Carica i dati dalla memoria se esistono
if os.path.exists(BASELINE_FILE):
    df = pd.read_csv(BASELINE_FILE)
    
    st.title("💼 Dashboard Portafoglio (Storico & Live)")
    
    tickers = df['Yahoo_Ticker'].dropna().unique().tolist()

    with st.spinner("Scaricamento storico completo (5 Anni) da Yahoo Finance..."):
        try:
            hist_data, fx_usd = fetch_historical_data(tickers)
            api_success = True
        except Exception as e:
            st.error("Errore di connessione a Yahoo Finance. Riprova tra poco.")
            api_success = False

    if api_success:
        results = []
        
        # Totali esatti derivanti dal file della Banca (Il tuo punto zero)
        tot_valore_carico_banca = df['Valore_Carico_CSV'].sum()
        
        for _, row in df.iterrows():
            t = row['Yahoo_Ticker']
            qty = float(row['Quantita'])
            valore_carico_asset = float(row.get('Valore_Carico_CSV', 0.0))
            valore_mercato_csv = float(row.get('Valore_Mercato_CSV', 0.0))
            
            if pd.isna(t) or qty == 0: continue
            
            try:
                # Estrazione serie storica per il ticker
                if len(tickers) == 1:
                    t_hist = hist_data['Close'].dropna()
                else:
                    if t not in hist_data.columns.levels[0]: continue
                    t_hist = hist_data[t]['Close'].dropna()
                    
                if t_hist.empty: continue
                
                # Prezzi nei vari intervalli temporali
                p_now = float(np.atleast_1d(t_hist.iloc[-1])[0])
                p_1d  = float(np.atleast_1d(t_hist.iloc[-2] if len(t_hist) > 2 else t_hist.iloc[0])[0])
                p_5d  = float(np.atleast_1d(t_hist.iloc[-6] if len(t_hist) > 6 else t_hist.iloc[0])[0])
                p_1m  = float(np.atleast_1d(t_hist.iloc[-22] if len(t_hist) > 22 else t_hist.iloc[0])[0])
                p_3m  = float(np.atleast_1d(t_hist.iloc[-64] if len(t_hist) > 64 else t_hist.iloc[0])[0])
                p_6m  = float(np.atleast_1d(t_hist.iloc[-126] if len(t_hist) > 126 else t_hist.iloc[0])[0])
                p_1y  = float(np.atleast_1d(t_hist.iloc[-252] if len(t_hist) > 252 else t_hist.iloc[0])[0])
                p_5y  = float(np.atleast_1d(t_hist.iloc[0])[0])
                
                # Conversione Valuta (Semplificata: converte in EUR se è un mercato extra-UE)
                is_eur = any(x in t for x in ['.MI', '.F', '.DE', '.PA', '.MC', '.AS'])
                fx = 1.0 if is_eur else (1 / fx_usd)
                
                # Valore Attuale Calcolato
                valore_attuale_live = qty * p_now * fx
                
                # Variazioni su base storica (P&L per periodi)
                pl_1d = qty * (p_now - p_1d) * fx
                pl_5d = qty * (p_now - p_5d) * fx
                pl_1m = qty * (p_now - p_1m) * fx
                pl_3m = qty * (p_now - p_3m) * fx
                pl_6m = qty * (p_now - p_6m) * fx
                pl_1y = qty * (p_now - p_1y) * fx
                pl_5y = qty * (p_now - p_5y) * fx
                
                # P&L TOTALE ESATTO = Valore Attuale Live - Valore di Carico originale della Banca!
                pl_totale = valore_attuale_live - valore_carico_asset
                
                results.append({
                    'Titolo': row['Titolo'],
                    'Ticker': t,
                    'Valore Carico (€)': valore_carico_asset,
                    'Valore Attuale (€)': valore_attuale_live,
                    'P&L Totale (€)': pl_totale,
                    '1 Giorno (€)': pl_1d,
                    '5 Giorni (€)': pl_5d,
                    '1 Mese (€)': pl_1m,
                    '3 Mesi (€)': pl_3m,
                    '6 Mesi (€)': pl_6m,
                    '1 Anno (€)': pl_1y,
                    '5 Anni (€)': pl_5y,
                })
            except Exception as e:
                continue
                
        df_res = pd.DataFrame(results)
        
        if not df_res.empty:
            st.markdown("### 🎯 KPI di Portafoglio")
            
            tot_attuale = df_res['Valore Attuale (€)'].sum()
            tot_pl = df_res['P&L Totale (€)'].sum()
            tot_pl_1d = df_res['1 Giorno (€)'].sum()
            tot_pl_1m = df_res['1 Mese (€)'].sum()
            tot_pl_1y = df_res['1 Anno (€)'].sum()
            
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Valore Attuale Live", f"€ {tot_attuale:,.2f}")
            c2.metric("P&L Totale Reale", f"€ {tot_pl:,.2f}")
            c3.metric("Oggi (1G)", f"€ {tot_pl_1d:,.0f}")
            c4.metric("1 Mese", f"€ {tot_pl_1m:,.0f}")
            c5.metric("1 Anno", f"€ {tot_pl_1y:,.0f}")

            st.markdown("---")
            
            # Grafico a barre per le performance di breve periodo
            st.markdown("#### 📊 Andamento Ultimi 30 Giorni (Top & Flop)")
            top_1m = df_res.sort_values(by='1 Mese (€)', ascending=False).head(10)
            fig_bar = px.bar(top_1m, x='1 Mese (€)', y='Titolo', orientation='h', color='1 Mese (€)', color_continuous_scale='Greens')
            st.plotly_chart(fig_bar, width='stretch')

            st.markdown("#### 📋 Tabella Dettagliata (Storico Temporale)")
            
            # Formattazione avanzata con gradiente di colore
            cols_to_color = ['P&L Totale (€)', '1 Giorno (€)', '5 Giorni (€)', '1 Mese (€)', '3 Mesi (€)', '6 Mesi (€)', '1 Anno (€)', '5 Anni (€)']
            
            st.dataframe(df_res.style.format({
                'Valore Carico (€)': '€ {:,.2f}',
                'Valore Attuale (€)': '€ {:,.2f}',
                'P&L Totale (€)': '€ {:,.2f}',
                '1 Giorno (€)': '€ {:,.0f}',
                '5 Giorni (€)': '€ {:,.0f}',
                '1 Mese (€)': '€ {:,.0f}',
                '3 Mesi (€)': '€ {:,.0f}',
                '6 Mesi (€)': '€ {:,.0f}',
                '1 Anno (€)': '€ {:,.0f}',
                '5 Anni (€)': '€ {:,.0f}'
            }).background_gradient(subset=cols_to_color, cmap='RdYlGn', vmin=-1000, vmax=1000), width='stretch')
            
            # Opzione per resettare
            if st.sidebar.button("🗑️ Elimina Portafoglio Memorizzato"):
                os.remove(BASELINE_FILE)
                st.rerun()

else:
    st.info("👋 Benvenuto! Per iniziare, carica il file `portafoglio-1103.CSV` dalla barra di sinistra. I dati verranno memorizzati per le visite future.")
