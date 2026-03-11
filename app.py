import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Portfolio Advanced Analytics", layout="wide", page_icon="📊")

# --- 2. FUNZIONI DI SUPPORTO ---
def map_ticker(row):
    """Mappa i codici del file banca ai Ticker di Yahoo Finance in modo intelligente"""
    sym = str(row['Simbolo']).strip()
    if pd.isna(sym) or sym == 'nan': return None
    
    # Override per ETF/Titoli specifici (basato sull'analisi del tuo portafoglio)
    overrides = {
        'MGT.MI': 'MGT.PA', 'OR.EQ': 'OR.PA', 'AHLA.EQ': 'AHLA.F', 'LCOP.MI': 'LCOP.L',
        'EMOVE.MI': 'ECAR.L', 'EURO.MI': 'SMEU.MI', 'HSTE.MI': '3033.HK', 'CHINA.MI': 'CC1.PA',
        '1EL.MI': 'EL.PA', '1ITX.MI': 'ITX.MC', 'BRK/B.N': 'BRK-B', 'OXY/WS.N': 'OXY',
        'REMX.MI': 'REMX', 'DAPP.MI': 'DAPP', '1NVDA.MI': 'NVDA', '1MU.MI': 'MU',
        '1GOOGL.MI': 'GOOGL', '1CALM.MI': 'CALM', '1AVGO.MI': 'AVGO', '1FDS.MI': 'FDS',
        'PHPD.MI': 'PHPD.MI', 'VBTC.FRA': 'VBTC.DE', 'VS0L.FRA': 'VS0L.DE', '2BTC.FRA':'2BTC.DE',
        'WETH.FRA': 'WETH.DE', 'VETH.FRA': 'VETH.DE', 'NOV.FRA':'NOV.F', '4COP.FRA':'4COP.DE'
    }
    if sym in overrides: return overrides[sym]
    
    # Gestione CFD
    if 'CFD' in sym:
        clean = sym.replace('.CFD', '').replace('CFD', '')
        if clean == 'RACE': return 'RACE.MI'
        return clean
    
    # Sostituzioni automatiche per mercati
    if sym.endswith('.O') or sym.endswith('.N') or sym.endswith('.OQ'): return sym.split('.')[0]
    if sym.endswith('.FRA'): return f"{sym.split('.')[0]}.DE"
    
    return sym

def pulisci_dati(df):
    """Rinomina le colonne formattate male (encoding) e converte i numeri italiani in float"""
    cols = df.columns.tolist()
    new_cols = []
    for c in cols:
        if 'Quantit' in c: new_cols.append('Quantita')
        elif 'P.zo medio di carico' in c: new_cols.append('Prezzo_Carico')
        elif 'Valore di carico' in c: new_cols.append('Valore_Carico')
        elif 'P.zo di mercato' in c: new_cols.append('Prezzo_Mercato')
        elif 'Valore di mercato' in c: new_cols.append('Valore_Mercato_EUR')
        elif 'Var%' in c: new_cols.append('Var_Perc')
        elif 'Var' in c and 'valuta' not in c and '%' not in c: new_cols.append('Var_EUR')
        else: new_cols.append(c)
    df.columns = new_cols

    def to_float(val):
        if pd.isna(val): return 0.0
        if isinstance(val, (int, float)): return float(val)
        try:
            return float(str(val).replace('.', '').replace(',', '.'))
        except: return 0.0

    for col in ['Quantita', 'Prezzo_Carico', 'Valore_Carico', 'Prezzo_Mercato', 'Valore_Mercato_EUR', 'Var_EUR', 'Var_Perc']:
        if col in df.columns:
            df[col] = df[col].apply(to_float)
            
    return df[df['Quantita'] > 0].copy()

# --- 3. INTERFACCIA E CARICAMENTO ---
st.title("📈 Advanced Portfolio Analytics")
st.markdown("Visualizzazione Storica, Tracking P&L e Analisi Multi-Periodo.")

# Caricamento del file tramite sidebar
uploaded_file = st.sidebar.file_uploader("Carica il tuo file CSV", type=['csv'])

if uploaded_file is not None:
    # 1. LETTURA DATI
    raw_df = pd.read_csv(uploaded_file, sep=';', encoding='latin1')
    df = pulisci_dati(raw_df)
    df['Yahoo_Ticker'] = df.apply(map_ticker, axis=1)
    
    tickers = df['Yahoo_Ticker'].dropna().unique().tolist()

    with st.spinner("Sincronizzazione prezzi storici (1 Anno) da Yahoo Finance in corso..."):
        # 2. SCARICAMENTO STORICO (Ultimo anno per calcolare i grafici)
        hist_data = yf.download(tickers, period="1y", group_by='ticker')
        
        # Scarico valute semplificato per conversione
        fx_usd = yf.download("EUR=X", period="1d")['Close'].iloc[-1] # Tasso USD/EUR
        
    st.success("Dati aggiornati con successo!")

    # 3. ELABORAZIONE STATISTICHE MULTI-PERIODO
    results = []
    
    for _, row in df.iterrows():
        t = row['Yahoo_Ticker']
        qty = row['Quantita']
        if pd.isna(t) or t not in hist_data: continue
        
        try:
            # Estrazione serie storica dei prezzi per il ticker
            if len(tickers) == 1:
                t_hist = hist_data['Close'].dropna()
            else:
                t_hist = hist_data[t]['Close'].dropna()
                
            if t_hist.empty: continue
            
            # Prezzi in istanti temporali diversi
            p_now = t_hist.iloc[-1]
            p_1m = t_hist.iloc[-21] if len(t_hist) > 21 else t_hist.iloc[0] # ~21 gg lavorativi in 1 mese
            p_3m = t_hist.iloc[-63] if len(t_hist) > 63 else t_hist.iloc[0] # ~63 gg lavorativi in 3 mesi
            p_6m = t_hist.iloc[-126] if len(t_hist) > 126 else t_hist.iloc[0]
            p_1y = t_hist.iloc[0]
            
            # Gestione valuta (Semplificata: EUR se ha estensione eu, altrimenti USD. GBP/HKD tollerati per calcoli approssimativi)
            is_eur = any(x in t for x in ['.MI', '.F', '.DE', '.PA', '.MC', '.AS'])
            fx_multiplier = 1.0 if is_eur else (1 / fx_usd)
            
            # Calcolo Valore Attuale EUR
            valore_eur = qty * p_now * fx_multiplier
            
            # P&L Assoluto in EUR per i diversi periodi
            pl_1m = qty * (p_now - p_1m) * fx_multiplier
            pl_3m = qty * (p_now - p_3m) * fx_multiplier
            pl_6m = qty * (p_now - p_6m) * fx_multiplier
            pl_1y = qty * (p_now - p_1y) * fx_multiplier
            
            results.append({
                'Titolo': row['Titolo'],
                'Mercato': row['Mercato'],
                'Valore Totale (€)': valore_eur,
                'P&L 1 Mese (€)': pl_1m,
                'P&L 3 Mesi (€)': pl_3m,
                'P&L 6 Mesi (€)': pl_6m,
                'P&L 1 Anno (€)': pl_1y,
            })
        except Exception as e:
            continue
            
    df_res = pd.DataFrame(results)
    
    if not df_res.empty:
        # --- 4. DASHBOARD KPI ---
        st.markdown("### 🎯 Sommari di Performance (Simulazione su allocazione corrente)")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Valore Attuale Mercato", f"€ {df_res['Valore Totale (€)'].sum():,.0f}")
        c2.metric("Variazione 1 Mese", f"€ {df_res['P&L 1 Mese (€)'].sum():,.0f}")
        c3.metric("Variazione 6 Mesi", f"€ {df_res['P&L 6 Mesi (€)'].sum():,.0f}")
        c4.metric("Variazione 1 Anno", f"€ {df_res['P&L 1 Anno (€)'].sum():,.0f}")

        st.markdown("---")

        # --- 5. GRAFICI ---
        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            st.markdown("#### 🏆 Performance 3 Mesi: Top 10 Titoli")
            top_3m = df_res.sort_values(by='P&L 3 Mesi (€)', ascending=False).head(10)
            fig1 = px.bar(top_3m, x='P&L 3 Mesi (€)', y='Titolo', orientation='h',
                          color='P&L 3 Mesi (€)', color_continuous_scale='Greens')
            fig1.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig1, use_container_width=True)

        with col_chart2:
            st.markdown("#### 🚨 Sofferenze 3 Mesi: Flop 10 Titoli")
            flop_3m = df_res.sort_values(by='P&L 3 Mesi (€)', ascending=True).head(10)
            fig2 = px.bar(flop_3m, x='P&L 3 Mesi (€)', y='Titolo', orientation='h',
                          color='P&L 3 Mesi (€)', color_continuous_scale='Reds_r')
            st.plotly_chart(fig2, use_container_width=True)

        st.markdown("#### 🗺️ Mappa ad Albero (Rischio e Asset Allocation)")
        # Treemap per vedere il peso sul totale (dimensione) e la performance a 1 anno (colore)
        fig_tree = px.treemap(df_res, path=['Mercato', 'Titolo'], values='Valore Totale (€)',
                              color='P&L 1 Anno (€)', color_continuous_scale='RdYlGn',
                              color_continuous_midpoint=0)
        fig_tree.update_layout(margin=dict(t=10, l=10, r=10, b=10))
        st.plotly_chart(fig_tree, use_container_width=True)

        # --- 6. TABELLA DETTAGLIATA INTERATTIVA ---
        st.markdown("#### 📋 Storico Dettagliato P/L")
        st.dataframe(df_res.style.format({
            'Valore Totale (€)': '€ {:,.2f}',
            'P&L 1 Mese (€)': '€ {:,.2f}',
            'P&L 3 Mesi (€)': '€ {:,.2f}',
            'P&L 6 Mesi (€)': '€ {:,.2f}',
            'P&L 1 Anno (€)': '€ {:,.2f}'
        }).background_gradient(subset=['P&L 1 Mese (€)', 'P&L 3 Mesi (€)', 'P&L 6 Mesi (€)', 'P&L 1 Anno (€)'], 
                               cmap='RdYlGn', vmin=-1000, vmax=1000), use_container_width=True)

else:
    st.info("👈 Carica il file `portafoglio-1103.CSV` dalla barra di sinistra per generare i grafici.")