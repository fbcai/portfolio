import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import numpy as np

st.set_page_config(page_title="Portfolio Ledger Analytics", layout="wide", page_icon="📚")

# --- 1. MAPPATURA ISIN -> TICKER YAHOO ---
ISIN_TO_TICKER = {
    'US67066G1040': 'NVDA',
    'US5951121038': 'MU',
    'IT0003121677': 'CE.MI',
    'US8740391003': 'TSM',
    'US6745991058': 'OXY',
    'US0378331005': 'AAPL',
    'US9497461015': 'WFC',
    'US4592001014': 'IBM',
    'FR0000120321': 'OR.PA',
    'NL00150001Q9': 'RACE.MI',
    'FR0007075494': 'MGT.PA',
    'JE00B1VS3002': 'PHPD.MI',
    'DE000A28M8D0': 'VBTC.DE',
    'DE000A3GSUD3': 'VS0L.DE',
    'CH0454664001': '2BTC.DE',
    'GB00BJYDH394': 'WETH.DE',
    'DE000A3GPSP7': 'VETH.DE',
    'IE0002PG6CA6': 'VVMX.DE', 
    'JE00BDD9QD91': 'LCOP.L',
    'IE0000ZL1RD2': 'SMH',
    'US7427181091': 'PG',
    'IT0005252207': 'CPR.MI',
    'US1280302027': 'CALM'
}

def map_isin_to_ticker(isin, titolo):
    if pd.isna(isin) or str(isin).strip() == '':
        titolo_upper = str(titolo).upper()
        if 'NEXTERA' in titolo_upper: return 'NEE'
        if 'NU RG-A' in titolo_upper: return 'NU'
        if 'BIOGEN' in titolo_upper: return 'BIIB'
        if 'UIPATH' in titolo_upper: return 'PATH'
        return None
    return ISIN_TO_TICKER.get(str(isin).strip(), None)

# --- 2. ELABORAZIONE DATI ---
def pulisci_numeri(val):
    if pd.isna(val) or str(val).strip() == '': return 0.0
    if isinstance(val, (int, float)): return float(val)
    try: return float(str(val).replace('.', '').replace(',', '.'))
    except: return 0.0

@st.cache_data
def elabora_transazioni(df_raw):
    df = df_raw.copy()
    colonne_num = ['Quantita', 'Prezzo', 'Cambio', 'Controvalore', 'Commissioni amministrato']
    for col in colonne_num:
        if col in df.columns:
            df[col] = df[col].apply(pulisci_numeri)
            
    df['Operazione'] = pd.to_datetime(df['Operazione'], format='%d/%m/%Y', errors='coerce')
    df = df.dropna(subset=['Operazione'])
    df = df.sort_values('Operazione').reset_index(drop=True)
    return df

# --- 3. MOTORE CONTABILE ---
def calcola_ledger(df):
    posizioni = {}
    for _, row in df.iterrows():
        isin = row['Isin']
        titolo = row['Titolo']
        chiave = str(isin).strip() if pd.notna(isin) and str(isin).strip() != '' else str(titolo).strip()
        
        if chiave not in posizioni:
            posizioni[chiave] = {
                'Titolo': titolo,
                'ISIN': isin if pd.notna(isin) else "",
                'Quantita_Attuale': 0.0,
                'Valore_Carico_Totale': 0.0,
                'Dividendi_Incassati': 0.0,
                'Commissioni_Totali': 0.0,
                'PL_Realizzato': 0.0
            }
            
        pos = posizioni[chiave]
        desc = str(row['Descrizione']).upper()
        segno = str(row['Segno']).strip().upper()
        controvalore = row['Controvalore']
        qty = row['Quantita']
        comm = row.get('Commissioni amministrato', 0.0)
        
        pos['Commissioni_Totali'] += comm
        
        if 'DIVIDENDO' in desc:
            pos['Dividendi_Incassati'] += controvalore
            
        elif 'COMPRAVENDITA' in desc:
            if segno == 'A':
                pos['Quantita_Attuale'] += qty
                pos['Valore_Carico_Totale'] += controvalore
            elif segno == 'V':
                if pos['Quantita_Attuale'] > 0:
                    pmc = pos['Valore_Carico_Totale'] / pos['Quantita_Attuale']
                    costo_del_venduto = pmc * qty
                    profitto = controvalore - costo_del_venduto
                    pos['PL_Realizzato'] += profitto
                    pos['Quantita_Attuale'] -= qty
                    pos['Valore_Carico_Totale'] -= costo_del_venduto
                else:
                    pos['PL_Realizzato'] += controvalore
                    
    risultati = []
    for k, v in posizioni.items():
        qty_att = round(v['Quantita_Attuale'], 4)
        risultati.append({
            'Chiave': k,
            'Titolo': v['Titolo'],
            'ISIN': v['ISIN'],
            'Quantita Attuale': qty_att,
            'Valore di Carico (€)': v['Valore_Carico_Totale'] if qty_att > 0.0001 else 0.0,
            'P&L Realizzato Storico (€)': v['PL_Realizzato'],
            'Dividendi Incassati (€)': v['Dividendi_Incassati'],
            'Commissioni Totali (€)': v['Commissioni_Totali']
        })
    return pd.DataFrame(risultati)

# --- 4. INTERFACCIA STREAMLIT ---
st.title("📚 Storico Transazioni & Analisi P&L")
st.markdown("Analisi completa del portafoglio: include le performance dei titoli attivi e di quelli già liquidati.")

uploaded_file = st.sidebar.file_uploader("Carica il file transazioni.CSV", type=['csv'])

if uploaded_file:
    df_raw = pd.read_csv(uploaded_file, sep=';', encoding='latin1')
    df_transazioni = elabora_transazioni(df_raw)
    
    st.sidebar.success(f"✅ {len(df_transazioni)} transazioni elaborate.")
    
    df_posizioni = calcola_ledger(df_transazioni)
    df_posizioni['Ticker'] = df_posizioni.apply(lambda x: map_isin_to_ticker(x['ISIN'], x['Titolo']), axis=1)
    
    tickers_da_cercare = df_posizioni[(df_posizioni['Quantita Attuale'] > 0) & (df_posizioni['Ticker'].notna())]['Ticker'].unique().tolist()
    
    with st.spinner("Scaricamento prezzi Live..."):
        try:
            live_data = yf.download(tickers_da_cercare, period="1d", group_by='ticker')
            fx_usd = float(yf.download("EUR=X", period="1d")['Close'].iloc[-1])
        except:
            live_data = None
            fx_usd = 1.08
            
    valori_mercato = []
    pl_latenti = []
    
    for _, row in df_posizioni.iterrows():
        qty = row['Quantita Attuale']
        t = row['Ticker']
        val_carico = row['Valore di Carico (€)']
        
        if qty > 0.0001 and live_data is not None and pd.notna(t) and t in live_data:
            try:
                if len(tickers_da_cercare) == 1:
                    p_now = float(np.atleast_1d(live_data['Close'].iloc[-1])[0])
                else:
                    p_now = float(np.atleast_1d(live_data[t]['Close'].iloc[-1])[0])
                
                is_eur = any(x in t for x in ['.MI', '.PA', '.DE', '.F', '.MC', '.AS'])
                fx = 1.0 if is_eur else (1 / fx_usd)
                
                v_mercato = qty * p_now * fx
                pl_latente = v_mercato - val_carico
            except:
                v_mercato = val_carico
                pl_latente = 0.0
        else:
            v_mercato = 0.0 if qty <= 0.0001 else val_carico
            pl_latente = 0.0
            
        valori_mercato.append(v_mercato)
        pl_latenti.append(pl_latente)
        
    df_posizioni['Valore Mercato (€)'] = valori_mercato
    df_posizioni['P&L Latente (€)'] = pl_latenti
    
    # --- INTERRUTTORI P&L ---
    st.sidebar.markdown("---")
    st.sidebar.header("⚙️ Impostazioni Rendimento")
    includi_dividendi = st.sidebar.checkbox("💰 Includi Dividendi", value=True)
    sottrai_commissioni = st.sidebar.checkbox("📉 Sottrai Commissioni", value=True)
    
    df_posizioni['P&L Netto Totale (€)'] = df_posizioni['P&L Latente (€)'] + df_posizioni['P&L Realizzato Storico (€)']
    
    if includi_dividendi:
        df_posizioni['P&L Netto Totale (€)'] += df_posizioni['Dividendi Incassati (€)']
    if sottrai_commissioni:
        df_posizioni['P&L Netto Totale (€)'] -= df_posizioni['Commissioni Totali (€)']

    # --- DIVISIONE PORTAFOGLI ---
    # Posizioni Aperte: Quantità > 0
    df_aperte = df_posizioni[df_posizioni['Quantita Attuale'] > 0.0001].copy()
    
    # Posizioni Chiuse: Quantità = 0 ma con P&L, Commissioni o Dividendi > 0
    df_chiuse = df_posizioni[(df_posizioni['Quantita Attuale'] <= 0.0001) & 
                             ((abs(df_posizioni['P&L Netto Totale (€)']) > 0.01) | 
                              (df_posizioni['Dividendi Incassati (€)'] > 0))].copy()

    # --- 5. DASHBOARD GLOBALE ---
    tot_mercato = df_aperte['Valore Mercato (€)'].sum()
    tot_pl_latente = df_aperte['P&L Latente (€)'].sum()
    tot_pl_realizzato = df_posizioni['P&L Realizzato Storico (€)'].sum() # Globale (Aperte + Chiuse)
    tot_dividendi = df_posizioni['Dividendi Incassati (€)'].sum() # Globale
    tot_netto_globale = df_posizioni['P&L Netto Totale (€)'].sum()
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Asset (Solo Posizioni Aperte)", f"€ {tot_mercato:,.2f}")
    c2.metric("P&L Latente (Aperte)", f"€ {tot_pl_latente:,.2f}")
    c3.metric("P&L Realizzato (Aperte + Chiuse)", f"€ {tot_pl_realizzato:,.2f}")
    c4.metric("Dividendi (Aperte + Chiuse)", f"€ {tot_dividendi:,.2f}")
    
    st.markdown("---")
    st.markdown(f"### 🏆 P&L NETTO GLOBALE STORICO: **€ {tot_netto_globale:,.2f}**")
    st.caption("Il vero profitto assoluto dal 2018: include le posizioni correnti e tutte le operazioni del passato.")
    
    # --- TABELLE SEPARATE (TABS) ---
    tab1, tab2 = st.tabs(["🟢 POSIZIONI APERTE (Attuali)", "🏁 POSIZIONI CHIUSE (Storico)"])
    
    with tab1:
        st.markdown("#### Portafoglio Attivo")
        col_view_aperte = ['Titolo', 'ISIN', 'Quantita Attuale', 'Valore di Carico (€)', 'Valore Mercato (€)', 
                           'P&L Latente (€)', 'P&L Realizzato Storico (€)', 'Dividendi Incassati (€)', 'P&L Netto Totale (€)']
        
        st.dataframe(df_aperte[col_view_aperte].style.format({
            'Quantita Attuale': '{:,.2f}',
            'Valore di Carico (€)': '€ {:,.2f}',
            'Valore Mercato (€)': '€ {:,.2f}',
            'P&L Latente (€)': '€ {:,.2f}',
            'P&L Realizzato Storico (€)': '€ {:,.2f}',
            'Dividendi Incassati (€)': '€ {:,.2f}',
            'P&L Netto Totale (€)': '€ {:,.2f}'
        }).background_gradient(subset=['P&L Netto Totale (€)', 'P&L Latente (€)', 'P&L Realizzato Storico (€)'], 
                               cmap='RdYlGn', vmin=-1000, vmax=1000), width='stretch')

    with tab2:
        st.markdown(f"#### Cimitero degli Investimenti (Contributo Totale: **€ {df_chiuse['P&L Netto Totale (€)'].sum():,.2f}**)")
        # Per le posizioni chiuse, non serve mostrare Quantità, Valore di Carico o P&L Latente
        col_view_chiuse = ['Titolo', 'ISIN', 'P&L Realizzato Storico (€)', 'Dividendi Incassati (€)', 'Commissioni Totali (€)', 'P&L Netto Totale (€)']
        
        st.dataframe(df_chiuse[col_view_chiuse].style.format({
            'P&L Realizzato Storico (€)': '€ {:,.2f}',
            'Dividendi Incassati (€)': '€ {:,.2f}',
            'Commissioni Totali (€)': '€ {:,.2f}',
            'P&L Netto Totale (€)': '€ {:,.2f}'
        }).background_gradient(subset=['P&L Netto Totale (€)', 'P&L Realizzato Storico (€)'], 
                               cmap='RdYlGn', vmin=-1000, vmax=1000), width='stretch')

else:
    st.info("👈 Carica il file storico `transazioni.CSV` per avviare il motore contabile.")
