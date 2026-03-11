import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import numpy as np

st.set_page_config(page_title="Gestione Portafoglio Attiva", layout="wide", page_icon="💼")

# --- 1. FUNZIONI DI SUPPORTO E MAPPING ---
def map_ticker(row):
    """Mappa i codici del CSV a Yahoo Finance (correzioni applicate)"""
    sym = str(row['Simbolo']).strip()
    if pd.isna(sym) or sym == 'nan': return None
    
    overrides = {
        'MGT.MI': 'MGT.PA', 'OR.EQ': 'OR.PA', 'AHLA.EQ': 'AHLA.F', 'LCOP.MI': 'LCOP.L',
        'EMOVE.MI': 'ECAR.L', 'EURO.MI': 'SMEU.MI', 'HSTE.MI': '3033.HK', 'CHINA.MI': 'CC1.PA',
        '1EL.MI': 'EL.PA', '1ITX.MI': 'ITX.MC', 'BRK/B.N': 'BRK-B', 'OXY/WS.N': 'OXY',
        'REMX.MI': 'VVMX.DE', 'DAPP.MI': 'DAPP.DE', '1NVDA.MI': 'NVDA', '1MU.MI': 'MU',
        '1GOOGL.MI': 'GOOGL', '1CALM.MI': 'CALM', '1AVGO.MI': 'AVGO', '1FDS.MI': 'FDS',
        'PHPD.MI': 'PHPD.MI', 'VBTC.FRA': 'VBTC.DE', 'VS0L.FRA': 'VS0L.DE', '2BTC.FRA':'2BTC.DE',
        'WETH.FRA': 'WETH.DE', 'VETH.FRA': 'VETH.DE', 'NOV.FRA':'NOV.F', '4COP.FRA':'4COP.DE',
        'GBSE.MI':'GBSE.MI', 'RACE.MI':'RACE.MI', 'CE.MI':'CE.MI', 'OXY.N': 'OXY', 'TSM.N': 'TSM'
    }
    if sym in overrides: return overrides[sym]
    
    if 'CFD' in sym:
        clean = sym.replace('.CFD', '').replace('CFD', '')
        return 'RACE.MI' if clean == 'RACE' else clean
    
    if sym.endswith('.O') or sym.endswith('.N') or sym.endswith('.OQ'): return sym.split('.')[0]
    if sym.endswith('.FRA'): return f"{sym.split('.')[0]}.DE"
    
    return sym

def pulisci_dati(df):
    """Estrae i valori ESATTI dal CSV per usarli come base sicura"""
    cols = df.columns.tolist()
    new_cols = []
    for c in cols:
        if 'Quantit' in c: new_cols.append('Quantita')
        elif 'P.zo medio di carico' in c: new_cols.append('Prezzo_Carico')
        elif 'Valore di carico' in c: new_cols.append('Valore_Carico')
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

    num_cols = ['Quantita', 'Prezzo_Carico', 'Valore_Carico', 'Prezzo_Mercato_CSV', 'Valore_Mercato_CSV', 'Var_EUR_CSV']
    for col in num_cols:
        if col in df.columns:
            df[col] = df[col].apply(to_float)
            
    return df[df['Quantita'] > 0].copy()

# --- 2. GESTIONE STATO (LIQUIDITÀ E TRANSAZIONI) ---
if 'liquidita' not in st.session_state:
    st.session_state.liquidita = 0.0
if 'transazioni' not in st.session_state:
    st.session_state.transazioni = pd.DataFrame(columns=['Data', 'Ticker', 'Tipo', 'Quantita', 'Prezzo', 'Controvalore'])

# --- 3. INTERFACCIA PRINCIPALE ---
st.title("💼 Portafoglio Live & Gestione Liquidità")
st.markdown("Baseline basata sui dati bancari (CSV) con Live Feed per tracking futuro e registrazione transazioni.")

# SIDEBAR: Gestione Liquidità e Nuove Transazioni
with st.sidebar:
    st.header("🏦 Gestione Cassa")
    nuova_cassa = st.number_input("Aggiungi/Preleva Fondi (€)", step=100.0, format="%.2f")
    if st.button("Aggiorna Liquidità"):
        st.session_state.liquidita += nuova_cassa
        st.success(f"Liquidità aggiornata! Nuovo saldo: € {st.session_state.liquidita:,.2f}")
    
    st.metric("Liquidità Disponibile", f"€ {st.session_state.liquidita:,.2f}")
    
    st.markdown("---")
    st.header("🔄 Registra Transazione")
    with st.form("form_transazione", clear_on_submit=True):
        t_ticker = st.text_input("Ticker (es. NVDA, CE.MI)")
        t_tipo = st.selectbox("Operazione", ["Acquisto", "Vendita"])
        t_qty = st.number_input("Quantità", min_value=0.01, step=1.0)
        t_prezzo = st.number_input("Prezzo Eseguito (in €)", min_value=0.01, step=1.0)
        submit_btn = st.form_submit_button("Registra Eseguito")
        
        if submit_btn and t_ticker:
            controvalore = t_qty * t_prezzo
            if t_tipo == "Acquisto" and controvalore > st.session_state.liquidita:
                st.error("Liquidità insufficiente!")
            else:
                nuova_tx = pd.DataFrame([{
                    'Data': pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
                    'Ticker': t_ticker.upper(),
                    'Tipo': t_tipo,
                    'Quantita': t_qty,
                    'Prezzo': t_prezzo,
                    'Controvalore': controvalore
                }])
                st.session_state.transazioni = pd.concat([st.session_state.transazioni, nuova_tx], ignore_index=True)
                
                # Aggiorna cassa
                if t_tipo == "Acquisto":
                    st.session_state.liquidita -= controvalore
                else:
                    st.session_state.liquidita += controvalore
                st.rerun()

uploaded_file = st.file_uploader("Carica il Portafoglio (portafoglio-1103.CSV)", type=['csv'])

if uploaded_file is not None:
    # Lettura e mappatura
    raw_df = pd.read_csv(uploaded_file, sep=';', encoding='latin1')
    df = pulisci_dati(raw_df)
    df['Yahoo_Ticker'] = df.apply(map_ticker, axis=1)
    
    # Integrazione delle transazioni recenti (aggiorna le quantità del CSV)
    tx_df = st.session_state.transazioni
    if not tx_df.empty:
        for _, tx in tx_df.iterrows():
            if tx['Ticker'] in df['Yahoo_Ticker'].values:
                idx = df[df['Yahoo_Ticker'] == tx['Ticker']].index[0]
                if tx['Tipo'] == "Acquisto":
                    df.at[idx, 'Quantita'] += tx['Quantita']
                    # Aggiorna valore di carico bancario sommandolo al nuovo acquisto
                    df.at[idx, 'Valore_Carico'] += tx['Controvalore']
                elif tx['Tipo'] == "Vendita":
                    df.at[idx, 'Quantita'] = max(0, df.at[idx, 'Quantita'] - tx['Quantita'])
            else:
                # Se è un titolo nuovo, lo aggiungiamo fittiziamente al dataframe (semplificato)
                pass 

    tickers = df['Yahoo_Ticker'].dropna().unique().tolist()

    with st.spinner("Scaricamento prezzi aggiornati (Live Feed) da Yahoo Finance..."):
        # Scarichiamo SOLO l'ultimo prezzo disponibile, non lo storico
        live_data = yf.download(tickers, period="1d", group_by='ticker')
        
        fx_data = yf.download("EUR=X", period="1d")['Close']
        fx_usd = float(fx_data.iloc[-1, 0]) if isinstance(fx_data, pd.DataFrame) else float(fx_data.iloc[-1])
            
    results = []
    
    # Valori Totali Originali della Banca (Fotografia)
    tot_valore_banca = df['Valore_Mercato_CSV'].sum()
    tot_pl_banca = df['Var_EUR_CSV'].sum()
    
    for _, row in df.iterrows():
        t = row['Yahoo_Ticker']
        qty = float(row['Quantita'])
        if qty == 0 or pd.isna(t) or t not in live_data: continue
        
        try:
            # Prezzo Live da Yahoo
            if len(tickers) == 1:
                p_now = float(np.atleast_1d(live_data['Close'].iloc[-1])[0])
            else:
                p_now = float(np.atleast_1d(live_data[t]['Close'].iloc[-1])[0])
            
            # Gestione Valuta
            is_eur = any(x in t for x in ['.MI', '.F', '.DE', '.PA', '.MC', '.AS'])
            fx_multiplier = 1.0 if is_eur else (1 / fx_usd)
            
            # Calcoli LIVE
            valore_eur_live = qty * p_now * fx_multiplier
            
            # Valori Originali CSV
            valore_eur_csv = float(row.get('Valore_Mercato_CSV', 0.0))
            pl_eur_csv = float(row.get('Var_EUR_CSV', 0.0))
            
            # PERFORMANCE FUTURA (Delta dal momento dell'esportazione CSV)
            delta_futuro = valore_eur_live - valore_eur_csv
            
            # P&L Totale Aggiornato = P&L Banca Originale + Movimento Live Recente
            pl_totale_aggiornato = pl_eur_csv + delta_futuro
            
            results.append({
                'Titolo': row['Titolo'],
                'Mercato': row['Mercato'],
                'Valore Banca Originale (€)': valore_eur_csv,
                'P&L Banca Storico (€)': pl_eur_csv,
                'Prezzo Live': p_now,
                'Valore Attuale Live (€)': valore_eur_live,
                'Delta Recente (Futuro) (€)': delta_futuro,
                'P&L Totale Live (€)': pl_totale_aggiornato
            })
        except Exception as e:
            continue
            
    df_res = pd.DataFrame(results)
    
    if not df_res.empty:
        st.markdown("### 📊 Cruscotto di Portafoglio")
        
        totale_investito = tot_valore_banca - tot_pl_banca
        tot_valore_live = df_res['Valore Attuale Live (€)'].sum()
        tot_pl_live = df_res['P&L Totale Live (€)'].sum()
        delta_complessivo = df_res['Delta Recente (Futuro) (€)'].sum()
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Valore Asset Live", f"€ {tot_valore_live:,.2f}", f"{delta_complessivo:,.2f} dal CSV")
        c2.metric("Liquidità in Cassa", f"€ {st.session_state.liquidita:,.2f}")
        c3.metric("P&L Totale (Live + Storico)", f"€ {tot_pl_live:,.2f}")
        c4.metric("Patrimonio Complessivo", f"€ {(tot_valore_live + st.session_state.liquidita):,.2f}")

        st.markdown("---")
        
        col_grafici1, col_grafici2 = st.columns(2)
        
        with col_grafici1:
            st.markdown("#### 🚀 Migliori Trend Recenti (Dal caricamento file)")
            top_recenti = df_res.sort_values(by='Delta Recente (Futuro) (€)', ascending=False).head(8)
            fig1 = px.bar(top_recenti, x='Delta Recente (Futuro) (€)', y='Titolo', orientation='h',
                          color='Delta Recente (Futuro) (€)', color_continuous_scale='Greens')
            fig1.update_layout(yaxis={'categoryorder':'total ascending'}, showlegend=False)
            st.plotly_chart(fig1, use_container_width=True)
            
        with col_grafici2:
            st.markdown("#### 🗺️ Asset Allocation Totale (Asset + Cassa)")
            # Prepariamo i dati inclusa la liquidità per il grafico a torta
            alloc_df = pd.DataFrame({
                'Asset': ['Portafoglio Titoli', 'Liquidità'],
                'Valore': [tot_valore_live, st.session_state.liquidita]
            })
            fig_pie = px.pie(alloc_df, values='Valore', names='Asset', hole=0.4, color_discrete_sequence=['#1f77b4', '#2ca02c'])
            st.plotly_chart(fig_pie, use_container_width=True)

        st.markdown("#### 📋 Tabella Dettaglio Posizioni (Ibrida CSV / Live)")
        
        cols_da_mostrare = ['Titolo', 'Valore Banca Originale (€)', 'P&L Banca Storico (€)', 
                            'Prezzo Live', 'Valore Attuale Live (€)', 'Delta Recente (Futuro) (€)', 'P&L Totale Live (€)']
                            
        st.dataframe(df_res[cols_da_mostrare].style.format({
            'Valore Banca Originale (€)': '€ {:,.2f}',
            'P&L Banca Storico (€)': '€ {:,.2f}',
            'Prezzo Live': '{:,.2f}',
            'Valore Attuale Live (€)': '€ {:,.2f}',
            'Delta Recente (Futuro) (€)': '€ {:,.2f}',
            'P&L Totale Live (€)': '€ {:,.2f}'
        }).background_gradient(subset=['P&L Banca Storico (€)', 'Delta Recente (Futuro) (€)', 'P&L Totale Live (€)'], 
                               cmap='RdYlGn', vmin=-500, vmax=500), use_container_width=True)
                               
        # Storico transazioni
        if not st.session_state.transazioni.empty:
            st.markdown("#### 🧾 Registro Transazioni Effettuate")
            st.dataframe(st.session_state.transazioni, use_container_width=True)

else:
    st.info("👈 Carica il file `portafoglio.csv` dalla barra di sinistra per generare la dashboard.")
