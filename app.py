import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import numpy as np

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Portfolio Advanced Analytics", layout="wide", page_icon="📊")

# --- 2. FUNZIONI DI SUPPORTO ---
def map_ticker(row):
    """Mappa i codici del file banca ai Ticker di Yahoo Finance in modo intelligente"""
    sym = str(row['Simbolo']).strip()
    if pd.isna(sym) or sym == 'nan': return None
    
    # Override per ETF/Titoli specifici 
    overrides = {
        'MGT.MI': 'MGT.PA', 'OR.EQ': 'OR.PA', 'AHLA.EQ': 'AHLA.F', 'LCOP.MI': 'LCOP.L',
        'EMOVE.MI': 'ECAR.L', 'EURO.MI': 'SMEU.MI', 'HSTE.MI': '3033.HK', 'CHINA.MI': 'CC1.PA',
        '1EL.MI': 'EL.PA', '1ITX.MI': 'ITX.MC', 'BRK/B.N': 'BRK-B', 'OXY/WS.N': 'OXY',
        'REMX.MI': 'VVMX.DE', 'DAPP.MI': 'DAPP.DE', '1NVDA.MI': 'NVDA', '1MU.MI': 'MU',
        '1GOOGL.MI': 'GOOGL', '1CALM.MI': 'CALM', '1AVGO.MI': 'AVGO', '1FDS.MI': 'FDS',
        'PHPD.MI': 'PHPD.MI', 'VBTC.FRA': 'VBTC.DE', 'VS0L.FRA': 'VS0L.DE', '2BTC.FRA':'2BTC.DE',
        'WETH.FRA': 'WETH.DE', 'VETH.FRA': 'VETH.DE', 'NOV.FRA':'NOV.F', '4COP.FRA':'4COP.DE',
        'GBSE.MI':'GBSE.MI', 'RACE.MI':'RACE.MI', 'CE.MI':'CE.MI'
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
    """Rinomina le colonne e converte i numeri italiani in float"""
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
st.markdown("Visualizzazione Storica, Tracking P&L e Analisi Multi-Periodo (Fino a 5 Anni).")

uploaded_file = st.sidebar.file_uploader("Carica il tuo file CSV (es. portafoglio-1103.CSV)", type=['csv'])

if uploaded_file is not None:
    # 1. LETTURA DATI
    raw_df = pd.read_csv(uploaded_file, sep=';', encoding='latin1')
    df = pulisci_dati(raw_df)
    df['Yahoo_Ticker'] = df.apply(map_ticker, axis=1)
    
    tickers = df['Yahoo_Ticker'].dropna().unique().tolist()

    with st.spinner("Sincronizzazione prezzi storici (5 Anni) da Yahoo Finance in corso..."):
        # 2. SCARICAMENTO STORICO (ESTESO A 5 ANNI)
        hist_data = yf.download(tickers, period="5y", group_by='ticker')
        
        fx_data = yf.download("EUR=X", period="1d")['Close']
        if isinstance(fx_data, pd.DataFrame):
            fx_usd = float(fx_data.iloc[-1, 0])
        else:
            fx_usd = float(fx_data.iloc[-1])
            
    st.success("Dati aggiornati con successo!")

    # 3. ELABORAZIONE STATISTICHE MULTI-PERIODO
    results = []
    
    for _, row in df.iterrows():
        t = row['Yahoo_Ticker']
        qty = float(row['Quantita'])
        valore_carico = float(row.get('Valore_Carico', 0.0)) # Costo storico esatto dal CSV
        
        if pd.isna(t) or t not in hist_data: continue
        
        try:
            if len(tickers) == 1:
                t_hist = hist_data['Close'].dropna()
            else:
                t_hist = hist_data[t]['Close'].dropna()
                
            if t_hist.empty: continue
            
            # FORZATURA DEI PREZZI A FLOAT
            p_now = float(np.atleast_1d(t_hist.iloc[-1])[0])
            
            # Calcolo degli indici temporali approssimativi per i mercati (21 gg al mese)
            p_1m = float(np.atleast_1d(t_hist.iloc[-21] if len(t_hist) > 21 else t_hist.iloc[0])[0])
            p_3m = float(np.atleast_1d(t_hist.iloc[-63] if len(t_hist) > 63 else t_hist.iloc[0])[0])
            p_6m = float(np.atleast_1d(t_hist.iloc[-126] if len(t_hist) > 126 else t_hist.iloc[0])[0])
            p_1y = float(np.atleast_1d(t_hist.iloc[-252] if len(t_hist) > 252 else t_hist.iloc[0])[0])
            p_5y = float(np.atleast_1d(t_hist.iloc[0])[0]) # Il valore più vecchio disponibile (max 5 anni)
            
            is_eur = any(x in t for x in ['.MI', '.F', '.DE', '.PA', '.MC', '.AS'])
            fx_multiplier = 1.0 if is_eur else (1 / fx_usd)
            
            # Calcolo Valore Attuale EUR e P&L
            valore_eur = float(qty * p_now * fx_multiplier)
            
            pl_1m = float(qty * (p_now - p_1m) * fx_multiplier)
            pl_3m = float(qty * (p_now - p_3m) * fx_multiplier)
            pl_6m = float(qty * (p_now - p_6m) * fx_multiplier)
            pl_1y = float(qty * (p_now - p_1y) * fx_multiplier)
            pl_5y = float(qty * (p_now - p_5y) * fx_multiplier)
            
            # P&L Totale Reale (Differenza tra valore mercato attuale e costo d'acquisto storico)
            pl_totale = valore_eur - valore_carico
            
            results.append({
                'Titolo': row['Titolo'],
                'Mercato': row['Mercato'],
                'Valore Totale (€)': valore_eur,
                'P&L 1 Mese (€)': pl_1m,
                'P&L 3 Mesi (€)': pl_3m,
                'P&L 6 Mesi (€)': pl_6m,
                'P&L 1 Anno (€)': pl_1y,
                'P&L 5 Anni (€)': pl_5y,
                'P&L Totale Reale (€)': pl_totale
            })
        except Exception as e:
            continue
            
    df_res = pd.DataFrame(results)
    
    if not df_res.empty:
        # --- 4. DASHBOARD KPI ---
        st.markdown("### 🎯 Sommari di Performance")
        
        # Suddivisi su 6 colonne per far entrare tutto
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Valore Attuale", f"€ {df_res['Valore Totale (€)'].sum():,.0f}")
        c2.metric("Var 1 Mese", f"€ {df_res['P&L 1 Mese (€)'].sum():,.0f}")
        c3.metric("Var 6 Mesi", f"€ {df_res['P&L 6 Mesi (€)'].sum():,.0f}")
        c4.metric("Var 1 Anno", f"€ {df_res['P&L 1 Anno (€)'].sum():,.0f}")
        c5.metric("Var 5 Anni", f"€ {df_res['P&L 5 Anni (€)'].sum():,.0f}")
        
        # Mettiamo in evidenza il P&L Totale Reale
        c6.metric("P&L TOTALE STORICO", f"€ {df_res['P&L Totale Reale (€)'].sum():,.0f}", delta_color="normal")

        st.markdown("---")

        # --- 5. GRAFICI ---
        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            st.markdown("#### 🏆 Performance 1 Anno: Top 10 Titoli")
            top_1y = df_res.sort_values(by='P&L 1 Anno (€)', ascending=False).head(10)
            fig1 = px.bar(top_1y, x='P&L 1 Anno (€)', y='Titolo', orientation='h',
                          color='P&L 1 Anno (€)', color_continuous_scale='Greens')
            fig1.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig1, use_container_width=True)

        with col_chart2:
            st.markdown("#### 🚨 Top Detrattori (P&L Totale Reale)")
            flop_tot = df_res.sort_values(by='P&L Totale Reale (€)', ascending=True).head(10)
            fig2 = px.bar(flop_tot, x='P&L Totale Reale (€)', y='Titolo', orientation='h',
                          color='P&L Totale Reale (€)', color_continuous_scale='Reds_r')
            st.plotly_chart(fig2, use_container_width=True)

        st.markdown("#### 🗺️ Mappa ad Albero (Asset Allocation pesata sul P&L Totale)")
        fig_tree = px.treemap(df_res, path=['Mercato', 'Titolo'], values='Valore Totale (€)',
                              color='P&L Totale Reale (€)', color_continuous_scale='RdYlGn',
                              color_continuous_midpoint=0)
        fig_tree.update_layout(margin=dict(t=10, l=10, r=10, b=10))
        st.plotly_chart(fig_tree, use_container_width=True)

        # --- 6. TABELLA DETTAGLIATA INTERATTIVA ---
        st.markdown("#### 📋 Storico Dettagliato P/L")
        
        # Colonne da colorare con mappa di calore
        gradient_cols = ['P&L 1 Mese (€)', 'P&L 3 Mesi (€)', 'P&L 6 Mesi (€)', 
                         'P&L 1 Anno (€)', 'P&L 5 Anni (€)', 'P&L Totale Reale (€)']
                         
        st.dataframe(df_res.style.format({
            'Valore Totale (€)': '€ {:,.2f}',
            'P&L 1 Mese (€)': '€ {:,.2f}',
            'P&L 3 Mesi (€)': '€ {:,.2f}',
            'P&L 6 Mesi (€)': '€ {:,.2f}',
            'P&L 1 Anno (€)': '€ {:,.2f}',
            'P&L 5 Anni (€)': '€ {:,.2f}',
            'P&L Totale Reale (€)': '€ {:,.2f}'
        }).background_gradient(subset=gradient_cols, cmap='RdYlGn', vmin=-1000, vmax=1000), use_container_width=True)

else:
    st.info("👈 Carica il file `portafoglio-1103.CSV` dalla barra di sinistra per generare i grafici.")
