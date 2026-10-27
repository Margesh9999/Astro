"""
Instrument Universe
===================
Curated, liquid, Yahoo-Finance-valid universe across markets and instrument
classes, powering the searchable / dropdown instrument picker:

  markets : US · UK · India · Europe · Japan · Crypto · FX
  types   : equity · etf · index · mutual_fund · crypto · currency

Each row: (symbol, name, sector, has_options)
  has_options=True  -> exchange-traded weekly/monthly options exist and are
                       liquid enough for the Options Lab (US listed + NSE F&O)
  has_options=False -> chart/quant analytics only (the lab can still model it
                       with a synthetic chain, clearly labelled)

Any other valid Yahoo symbol can still be typed manually in the picker
(custom-symbol fallback), so the curated list is a convenience, not a cage.
Educational use only.
"""
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# (symbol, name, sector, has_options)
_MARKETS: Dict[str, Dict] = {
    "US": {
        "flag": "🇺🇸", "ccy": "USD",
        "equity": [
            ("AAPL", "Apple Inc.", "Technology", True),
            ("MSFT", "Microsoft Corp.", "Technology", True),
            ("NVDA", "NVIDIA Corp.", "Technology", True),
            ("AMZN", "Amazon.com Inc.", "Consumer Disc.", True),
            ("GOOGL", "Alphabet Inc. A", "Technology", True),
            ("META", "Meta Platforms", "Technology", True),
            ("TSLA", "Tesla Inc.", "Consumer Disc.", True),
            ("AVGO", "Broadcom Inc.", "Technology", True),
            ("ADBE", "Adobe Inc.", "Technology", True),
            ("CRM", "Salesforce Inc.", "Technology", True),
            ("ORCL", "Oracle Corp.", "Technology", True),
            ("CSCO", "Cisco Systems", "Technology", True),
            ("ACN", "Accenture plc", "Technology", True),
            ("AMD", "Advanced Micro Devices", "Technology", True),
            ("INTC", "Intel Corp.", "Technology", True),
            ("QCOM", "Qualcomm Inc.", "Technology", True),
            ("TXN", "Texas Instruments", "Technology", True),
            ("IBM", "IBM Corp.", "Technology", True),
            ("MU", "Micron Technology", "Technology", True),
            ("ANET", "Arista Networks", "Technology", True),
            ("PLTR", "Palantir Technologies", "Technology", True),
            ("SNOW", "Snowflake Inc.", "Technology", True),
            ("TSM", "Taiwan Semiconductor ADR", "Technology", True),
            ("ASML", "ASML Holding ADR", "Technology", True),
            ("BRK-B", "Berkshire Hathaway B", "Financials", True),
            ("JPM", "JPMorgan Chase", "Financials", True),
            ("V", "Visa Inc.", "Financials", True),
            ("MA", "Mastercard Inc.", "Financials", True),
            ("BAC", "Bank of America", "Financials", True),
            ("WFC", "Wells Fargo", "Financials", True),
            ("GS", "Goldman Sachs", "Financials", True),
            ("MS", "Morgan Stanley", "Financials", True),
            ("SCHW", "Charles Schwab", "Financials", True),
            ("BLK", "BlackRock Inc.", "Financials", True),
            ("C", "Citigroup Inc.", "Financials", True),
            ("AXP", "American Express", "Financials", True),
            ("SPGI", "S&P Global Inc.", "Financials", True),
            ("PGR", "Progressive Corp.", "Financials", True),
            ("UNH", "UnitedHealth Group", "Healthcare", True),
            ("LLY", "Eli Lilly & Co.", "Healthcare", True),
            ("JNJ", "Johnson & Johnson", "Healthcare", True),
            ("ABBV", "AbbVie Inc.", "Healthcare", True),
            ("MRK", "Merck & Co.", "Healthcare", True),
            ("PFE", "Pfizer Inc.", "Healthcare", True),
            ("TMO", "Thermo Fisher", "Healthcare", True),
            ("ABT", "Abbott Laboratories", "Healthcare", True),
            ("DHR", "Danaher Corp.", "Healthcare", True),
            ("AMGN", "Amgen Inc.", "Healthcare", True),
            ("MDT", "Medtronic plc", "Healthcare", True),
            ("GILD", "Gilead Sciences", "Healthcare", True),
            ("ISRG", "Intuitive Surgical", "Healthcare", True),
            ("CVS", "CVS Health", "Healthcare", True),
            ("ELV", "Elevance Health", "Healthcare", True),
            ("XOM", "Exxon Mobil", "Energy", True),
            ("CVX", "Chevron Corp.", "Energy", True),
            ("COP", "ConocoPhillips", "Energy", True),
            ("SLB", "SLB (Schlumberger)", "Energy", True),
            ("OXY", "Occidental Petroleum", "Energy", True),
            ("EOG", "EOG Resources", "Energy", True),
            ("CAT", "Caterpillar Inc.", "Industrials", True),
            ("UNP", "Union Pacific", "Industrials", True),
            ("RTX", "RTX Corp.", "Industrials", True),
            ("BA", "Boeing Co.", "Industrials", True),
            ("GE", "GE Aerospace", "Industrials", True),
            ("HON", "Honeywell Intl.", "Industrials", True),
            ("LMT", "Lockheed Martin", "Industrials", True),
            ("DE", "Deere & Co.", "Industrials", True),
            ("UPS", "United Parcel Service", "Industrials", True),
            ("ETN", "Eaton Corp.", "Industrials", True),
            ("HD", "Home Depot", "Consumer Disc.", True),
            ("WMT", "Walmart Inc.", "Consumer Staples", True),
            ("COST", "Costco Wholesale", "Consumer Staples", True),
            ("PG", "Procter & Gamble", "Consumer Staples", True),
            ("KO", "Coca-Cola Co.", "Consumer Staples", True),
            ("PEP", "PepsiCo Inc.", "Consumer Staples", True),
            ("MCD", "McDonald's Corp.", "Consumer Disc.", True),
            ("NKE", "Nike Inc.", "Consumer Disc.", True),
            ("TJX", "TJX Companies", "Consumer Disc.", True),
            ("LOW", "Lowe's Companies", "Consumer Disc.", True),
            ("SBUX", "Starbucks Corp.", "Consumer Disc.", True),
            ("TGT", "Target Corp.", "Consumer Disc.", True),
            ("F", "Ford Motor Co.", "Consumer Disc.", True),
            ("GM", "General Motors", "Consumer Disc.", True),
            ("DIS", "Walt Disney Co.", "Communication", True),
            ("NFLX", "Netflix Inc.", "Communication", True),
            ("CMCSA", "Comcast Corp.", "Communication", True),
            ("T", "AT&T Inc.", "Communication", True),
            ("VZ", "Verizon Communications", "Communication", True),
            ("TMUS", "T-Mobile US", "Communication", True),
            ("PM", "Philip Morris Intl.", "Consumer Staples", True),
            ("MO", "Altria Group", "Consumer Staples", True),
            ("MDLZ", "Mondelez Intl.", "Consumer Staples", True),
            ("CL", "Colgate-Palmolive", "Consumer Staples", True),
            ("LIN", "Linde plc", "Materials", True),
            ("SHW", "Sherwin-Williams", "Materials", True),
            ("APD", "Air Products", "Materials", True),
            ("NEM", "Newmont Corp.", "Materials", True),
            ("FCX", "Freeport-McMoRan", "Materials", True),
            ("NEE", "NextEra Energy", "Utilities", True),
            ("DUK", "Duke Energy", "Utilities", True),
            ("SO", "Southern Co.", "Utilities", True),
            ("PLD", "Prologis Inc.", "Real Estate", True),
            ("AMT", "American Tower", "Real Estate", True),
            ("SPG", "Simon Property Group", "Real Estate", True),
            ("UBER", "Uber Technologies", "Technology", True),
            ("ABNB", "Airbnb Inc.", "Consumer Disc.", True),
            ("HOOD", "Robinhood Markets", "Financials", True),
            ("COIN", "Coinbase Global", "Financials", True),
            ("SOFI", "SoFi Technologies", "Financials", True),
            ("RIVN", "Rivian Automotive", "Consumer Disc.", True),
            ("BABA", "Alibaba Group ADR", "Consumer Disc.", True),
            ("NIO", "NIO Inc. ADR", "Consumer Disc.", True),
            ("SHOP", "Shopify Inc.", "Technology", True),
        ],
        "etf": [
            ("SPY", "SPDR S&P 500 ETF", "Broad Market", True),
            ("QQQ", "Invesco QQQ Trust", "Broad Market", True),
            ("IWM", "iShares Russell 2000", "Small Cap", True),
            ("DIA", "SPDR Dow Jones IA", "Broad Market", True),
            ("VTI", "Vanguard Total Market", "Broad Market", True),
            ("VOO", "Vanguard S&P 500", "Broad Market", True),
            ("IVV", "iShares Core S&P 500", "Broad Market", True),
            ("VXUS", "Vanguard Total Intl", "International", True),
            ("VEA", "Vanguard Developed Mkts", "International", True),
            ("VWO", "Vanguard Emerging Mkts", "International", True),
            ("EEM", "iShares MSCI Emerging", "International", True),
            ("EFA", "iShares MSCI EAFE", "International", True),
            ("INDA", "iShares MSCI India", "International", True),
            ("EWJ", "iShares MSCI Japan", "International", True),
            ("FXI", "iShares China Large-Cap", "International", True),
            ("KWEB", "KraneShares China Internet", "International", True),
            ("EWZ", "iShares MSCI Brazil", "International", True),
            ("TLT", "iShares 20+ Yr Treasury", "Bonds", True),
            ("IEF", "iShares 7-10 Yr Treasury", "Bonds", True),
            ("SHY", "iShares 1-3 Yr Treasury", "Bonds", True),
            ("LQD", "iShares Inv. Grade Corp", "Bonds", True),
            ("HYG", "iShares High Yield Corp", "Bonds", True),
            ("JNK", "SPDR High Yield Bond", "Bonds", True),
            ("TIP", "iShares TIPS Bond", "Bonds", True),
            ("AGG", "iShares Core US Agg Bond", "Bonds", True),
            ("GLD", "SPDR Gold Shares", "Commodities", True),
            ("SLV", "iShares Silver Trust", "Commodities", True),
            ("USO", "United States Oil Fund", "Commodities", True),
            ("UNG", "United States Nat Gas Fund", "Commodities", True),
            ("GDX", "VanEck Gold Miners", "Commodities", True),
            ("XLE", "Energy Select SPDR", "Sector", True),
            ("XLF", "Financials Select SPDR", "Sector", True),
            ("XLI", "Industrials Select SPDR", "Sector", True),
            ("XLV", "Health Care Select SPDR", "Sector", True),
            ("XLK", "Technology Select SPDR", "Sector", True),
            ("XLY", "Cons. Discretionary SPDR", "Sector", True),
            ("XLP", "Cons. Staples SPDR", "Sector", True),
            ("XLU", "Utilities Select SPDR", "Sector", True),
            ("XLB", "Materials Select SPDR", "Sector", True),
            ("XLC", "Communication Svcs SPDR", "Sector", True),
            ("XLRE", "Real Estate Select SPDR", "Sector", True),
            ("SMH", "VanEck Semiconductor", "Sector", True),
            ("XBI", "SPDR Biotech ETF", "Sector", True),
            ("KRE", "SPDR Regional Banking", "Sector", True),
            ("ARKK", "ARK Innovation ETF", "Thematic", True),
            ("IBIT", "iShares Bitcoin Trust", "Thematic", True),
            ("UVXY", "ProShares Ultra VIX", "Volatility", True),
        ],
        "index": [
            ("^GSPC", "S&P 500", "US Large Cap", False),
            ("^IXIC", "NASDAQ Composite", "US Broad", False),
            ("^DJI", "Dow Jones Industrial", "US Blue Chip", False),
            ("^NDX", "NASDAQ 100", "US Large Cap", False),
            ("^RUT", "Russell 2000", "US Small Cap", False),
            ("^VIX", "CBOE Volatility Index", "Volatility", False),
        ],
        "mutual_fund": [
            ("FXAIX", "Fidelity 500 Index Fund", "US Large Cap", False),
            ("VFIAX", "Vanguard 500 Index Admiral", "US Large Cap", False),
            ("VTSAX", "Vanguard Total Stock Mkt Adm", "US Broad", False),
            ("VTIAX", "Vanguard Total Intl Stock Adm", "International", False),
            ("FCNTX", "Fidelity Contrafund", "US Growth", False),
            ("AGTHX", "American Funds Growth Fund", "US Growth", False),
            ("PONDX", "PIMCO Income Fund", "Bonds", False),
            ("VWINX", "Vanguard Wellesley Income", "Balanced", False),
        ],
    },
    "UK": {
        "flag": "🇬🇧", "ccy": "GBP",
        "equity": [
            ("SHEL.L", "Shell plc", "Energy", False),
            ("BP.L", "BP plc", "Energy", False),
            ("AZN.L", "AstraZeneca plc", "Healthcare", False),
            ("GSK.L", "GSK plc", "Healthcare", False),
            ("HSBA.L", "HSBC Holdings", "Financials", False),
            ("BARC.L", "Barclays plc", "Financials", False),
            ("LLOY.L", "Lloyds Banking Group", "Financials", False),
            ("NWG.L", "NatWest Group", "Financials", False),
            ("STAN.L", "Standard Chartered", "Financials", False),
            ("PRU.L", "Prudential plc", "Financials", False),
            ("AV.L", "Aviva plc", "Financials", False),
            ("RIO.L", "Rio Tinto plc", "Materials", False),
            ("AAL.L", "Anglo American plc", "Materials", False),
            ("GLEN.L", "Glencore plc", "Materials", False),
            ("ULVR.L", "Unilever plc", "Consumer Staples", False),
            ("BATS.L", "British American Tobacco", "Consumer Staples", False),
            ("DGE.L", "Diageo plc", "Consumer Staples", False),
            ("TSCO.L", "Tesco plc", "Consumer Staples", False),
            ("SBRY.L", "Sainsbury (J) plc", "Consumer Staples", False),
            ("VOD.L", "Vodafone Group", "Communication", False),
            ("BT-A.L", "BT Group plc", "Communication", False),
            ("REL.L", "RELX plc", "Media", False),
            ("LSEG.L", "London Stock Exchange Grp", "Financials", False),
            ("PSON.L", "Pearson plc", "Media", False),
            ("WPP.L", "WPP plc", "Media", False),
            ("NG.L", "National Grid plc", "Utilities", False),
            ("SVT.L", "Severn Trent plc", "Utilities", False),
            ("RR.L", "Rolls-Royce Holdings", "Industrials", False),
            ("BA.L", "BAE Systems plc", "Industrials", False),
            ("SMIN.L", "Smiths Group plc", "Industrials", False),
            ("EXPN.L", "Experian plc", "Industrials", False),
            ("HLMA.L", "Halma plc", "Industrials", False),
            ("CPG.L", "Compass Group plc", "Consumer Disc.", False),
            ("III.L", "3i Group plc", "Financials", False),
            ("FRES.L", "Fresnillo plc", "Materials", False),
            ("ICP.L", "Intertek Group plc", "Industrials", False),
        ],
        "etf": [
            ("ISF.L", "iShares Core FTSE 100", "UK Large Cap", False),
            ("CUKX.L", "iShares FTSE 100 (CW)", "UK Large Cap", False),
            ("VMID.L", "Vanguard FTSE 250", "UK Mid Cap", False),
            ("IUSA.L", "iShares Core S&P 500", "US Large Cap", False),
            ("VUSA.L", "Vanguard S&P 500 (GBP)", "US Large Cap", False),
            ("VUAG.L", "Vanguard Nasdaq-100 (GBP)", "US Growth", False),
            ("ERNS.L", "iShares £ Ultrashort Bond", "Cash+", False),
            ("IGLT.L", "iShares Core UK Gilts", "Bonds", False),
        ],
        "index": [
            ("^FTSE", "FTSE 100", "UK Large Cap", False),
            ("^FTMC", "FTSE Mid 250", "UK Mid Cap", False),
        ],
    },
    "India": {
        "flag": "🇮🇳", "ccy": "INR",
        "equity": [
            ("RELIANCE.NS", "Reliance Industries", "Energy", True),
            ("TCS.NS", "Tata Consultancy Services", "IT", True),
            ("HDFCBANK.NS", "HDFC Bank", "Financials", True),
            ("ICICIBANK.NS", "ICICI Bank", "Financials", True),
            ("INFY.NS", "Infosys Ltd", "IT", True),
            ("HINDUNILVR.NS", "Hindustan Unilever", "Consumer Staples", True),
            ("ITC.NS", "ITC Ltd", "Consumer Staples", True),
            ("SBIN.NS", "State Bank of India", "Financials", True),
            ("BHARTIARTL.NS", "Bharti Airtel", "Communication", True),
            ("KOTAKBANK.NS", "Kotak Mahindra Bank", "Financials", True),
            ("LT.NS", "Larsen & Toubro", "Industrials", True),
            ("AXISBANK.NS", "Axis Bank", "Financials", True),
            ("ASIANPAINT.NS", "Asian Paints", "Materials", True),
            ("MARUTI.NS", "Maruti Suzuki", "Automobile", True),
            ("TITAN.NS", "Titan Company", "Consumer Disc.", True),
            ("SUNPHARMA.NS", "Sun Pharmaceutical", "Healthcare", True),
            ("ULTRACEMCO.NS", "UltraTech Cement", "Materials", True),
            ("NTPC.NS", "NTPC Ltd", "Utilities", True),
            ("POWERGRID.NS", "Power Grid Corp", "Utilities", True),
            ("ONGC.NS", "Oil & Natural Gas Corp", "Energy", True),
            ("COALINDIA.NS", "Coal India", "Energy", True),
            ("TATASTEEL.NS", "Tata Steel", "Materials", True),
            ("JSWSTEEL.NS", "JSW Steel", "Materials", True),
            ("HINDALCO.NS", "Hindalco Industries", "Materials", True),
            ("VEDL.NS", "Vedanta Ltd", "Materials", True),
            ("GRASIM.NS", "Grasim Industries", "Materials", True),
            ("ADANIENT.NS", "Adani Enterprises", "Conglomerate", True),
            ("ADANIPORTS.NS", "Adani Ports & SEZ", "Industrials", True),
            ("BAJFINANCE.NS", "Bajaj Finance", "Financials", True),
            ("BAJAJFINSV.NS", "Bajaj Finserv", "Financials", True),
            ("M&M.NS", "Mahindra & Mahindra", "Automobile", True),
            ("TECHM.NS", "Tech Mahindra", "IT", True),
            ("HCLTECH.NS", "HCL Technologies", "IT", True),
            ("WIPRO.NS", "Wipro Ltd", "IT", True),
            ("DRREDDY.NS", "Dr Reddy's Labs", "Healthcare", True),
            ("CIPLA.NS", "Cipla Ltd", "Healthcare", True),
            ("DIVISLAB.NS", "Divi's Laboratories", "Healthcare", True),
            ("NESTLEIND.NS", "Nestle India", "Consumer Staples", True),
            ("BRITANNIA.NS", "Britannia Industries", "Consumer Staples", True),
            ("TATAMOTORS.NS", "Tata Motors", "Automobile", True),
            ("TATAPOWER.NS", "Tata Power", "Utilities", True),
            ("HAL.NS", "Hindustan Aeronautics", "Defence", True),
            ("BEL.NS", "Bharat Electronics", "Defence", True),
            ("IRCTC.NS", "IRCTC Ltd", "Travel", True),
            ("IRFC.NS", "Indian Railway Finance", "Financials", True),
            ("ZOMATO.NS", "Zomato Ltd (Eternal)", "Internet", True),
            ("DMART.NS", "Avenue Supermarts", "Retail", True),
            ("TRENT.NS", "Trent Ltd", "Retail", True),
            ("DLF.NS", "DLF Ltd", "Real Estate", True),
            ("PIDILITIND.NS", "Pidilite Industries", "Materials", True),
            ("SIEMENS.NS", "Siemens India", "Industrials", True),
            ("ABB.NS", "ABB India", "Industrials", True),
            ("HAVELLS.NS", "Havells India", "Consumer Disc.", True),
            ("INDIGO.NS", "InterGlobe Aviation", "Travel", True),
            ("INDUSINDBK.NS", "IndusInd Bank", "Financials", True),
            ("FEDERALBNK.NS", "Federal Bank", "Financials", True),
            ("IDFCFIRSTB.NS", "IDFC First Bank", "Financials", True),
            ("LICI.NS", "Life Insurance Corp", "Financials", True),
            ("BPCL.NS", "Bharat Petroleum", "Energy", True),
            ("IOC.NS", "Indian Oil Corp", "Energy", True),
            ("GAIL.NS", "GAIL India", "Energy", True),
            ("PFC.NS", "Power Finance Corp", "Financials", True),
            ("RECLTD.NS", "REC Ltd", "Financials", True),
            ("SAIL.NS", "Steel Authority of India", "Materials", True),
            ("JIOFIN.NS", "Jio Financial Services", "Financials", True),
            ("SHRIRAMFIN.NS", "Shriram Finance", "Financials", True),
            ("CHOLAFIN.NS", "Cholamandalam Invest", "Financials", True),
            ("HDFCAMC.NS", "HDFC Asset Mgmt", "Financials", True),
            ("SBILIFE.NS", "SBI Life Insurance", "Financials", True),
            ("HDFCLIFE.NS", "HDFC Life Insurance", "Financials", True),
            ("APOLLOHOSP.NS", "Apollo Hospitals", "Healthcare", True),
            ("MAXHEALTH.NS", "Max Healthcare", "Healthcare", True),
        ],
        "etf": [
            ("NIFTYBEES.NS", "Nippon Nifty 50 ETF", "Index ETF", False),
            ("BANKBEES.NS", "Nippon Bank Nifty ETF", "Index ETF", False),
            ("JUNIORBEES.NS", "Nippon Nifty Next 50", "Index ETF", False),
            ("GOLDBEES.NS", "Nippon Gold ETF", "Commodities", False),
            ("SILVERBEES.NS", "Nippon Silver ETF", "Commodities", False),
            ("ITBEES.NS", "Nippon Nifty IT ETF", "Sector ETF", False),
            ("PSUBNKBEES.NS", "Nippon PSU Bank ETF", "Sector ETF", False),
            ("MOM100.NS", "Motilal Nifty Midcap 100", "Index ETF", False),
            ("LIQUIDBEES.NS", "Nippon Liquid ETF", "Cash+", False),
        ],
        "index": [
            ("^NSEI", "Nifty 50", "India Large Cap", False),
            ("^NSEBANK", "Nifty Bank", "India Financials", False),
            ("^CNXIT", "Nifty IT", "India Tech", False),
        ],
    },
    "Europe": {
        "flag": "🇪🇺", "ccy": "EUR",
        "equity": [
            ("SAP.DE", "SAP SE", "Technology", False),
            ("SIE.DE", "Siemens AG", "Industrials", False),
            ("ALV.DE", "Allianz SE", "Financials", False),
            ("DTE.DE", "Deutsche Telekom", "Communication", False),
            ("BAS.DE", "BASF SE", "Materials", False),
            ("BMW.DE", "BMW AG", "Automobile", False),
            ("ASML.AS", "ASML Holding NV", "Technology", False),
            ("AD.AS", "Adyen NV", "Financials", False),
            ("HEIA.AS", "Heineken NV", "Consumer Staples", False),
            ("ING.AS", "ING Groep NV", "Financials", False),
            ("MC.PA", "LVMH", "Consumer Disc.", False),
            ("OR.PA", "L'Oreal SA", "Consumer Staples", False),
            ("TTE.PA", "TotalEnergies SE", "Energy", False),
            ("AIR.PA", "Airbus SE", "Industrials", False),
            ("BNP.PA", "BNP Paribas", "Financials", False),
            ("SAN.PA", "Sanofi SA", "Healthcare", False),
            ("NESN.SW", "Nestle SA", "Consumer Staples", False),
            ("NOVN.SW", "Novartis AG", "Healthcare", False),
            ("NOVO-B.CO", "Novo Nordisk B", "Healthcare", False),
            ("EQNR.OL", "Equinor ASA", "Energy", False),
        ],
        "index": [
            ("^GDAXI", "DAX 40 (Germany)", "Europe Large Cap", False),
            ("^FCHI", "CAC 40 (France)", "Europe Large Cap", False),
            ("^STOXX50E", "Euro Stoxx 50", "Europe Blue Chip", False),
        ],
    },
    "Japan": {
        "flag": "🇯🇵", "ccy": "JPY",
        "equity": [
            ("7203.T", "Toyota Motor Corp", "Automobile", False),
            ("6758.T", "Sony Group Corp", "Technology", False),
            ("9984.T", "SoftBank Group", "Technology", False),
            ("9432.T", "Nippon Telegraph & Tel", "Communication", False),
            ("8306.T", "Mitsubishi UFJ Finl", "Financials", False),
            ("6861.T", "Keyence Corp", "Technology", False),
            ("9983.T", "Fast Retailing", "Retail", False),
            ("6501.T", "Hitachi Ltd", "Industrials", False),
        ],
        "index": [
            ("^N225", "Nikkei 225", "Japan Large Cap", False),
        ],
    },
    "Crypto": {
        "flag": "🌐", "ccy": "USD",
        "crypto": [
            ("BTC-USD", "Bitcoin", "Layer 1", False),
            ("ETH-USD", "Ethereum", "Layer 1", False),
            ("SOL-USD", "Solana", "Layer 1", False),
            ("BNB-USD", "BNB", "Exchange", False),
            ("XRP-USD", "XRP", "Payments", False),
            ("ADA-USD", "Cardano", "Layer 1", False),
            ("DOGE-USD", "Dogecoin", "Meme", False),
            ("AVAX-USD", "Avalanche", "Layer 1", False),
            ("LINK-USD", "Chainlink", "Oracle", False),
            ("LTC-USD", "Litecoin", "Payments", False),
        ],
    },
    "FX": {
        "flag": "💱", "ccy": "USD",
        "currency": [
            ("GBPUSD=X", "GBP / USD", "Majors", False),
            ("EURUSD=X", "EUR / USD", "Majors", False),
            ("USDJPY=X", "USD / JPY", "Majors", False),
            ("USDINR=X", "USD / INR", "Emerging", False),
            ("GBPINR=X", "GBP / INR", "Emerging", False),
            ("GC=F", "Gold Futures (COMEX)", "Commodities", False),
        ],
    },
}

_MARKET_ORDER = ["US", "UK", "India", "Europe", "Japan", "Crypto", "FX"]
_TYPE_ORDER = ["equity", "etf", "index", "mutual_fund", "crypto", "currency"]
_TYPE_LABEL = {
    "equity": "Equity", "etf": "ETF", "index": "Index",
    "mutual_fund": "Mutual Fund", "crypto": "Crypto", "currency": "Currency",
}
_MARKET_LABEL = {m: m for m in _MARKET_ORDER}


def _flatten() -> List[dict]:
    rows = []
    for mk in _MARKET_ORDER:
        meta = _MARKETS[mk]
        for typ in _TYPE_ORDER:
            for sym, name, sector, has_opt in meta.get(typ, []):
                rows.append({
                    "symbol": sym,
                    "name": name,
                    "market": mk,
                    "market_label": _MARKET_LABEL[mk],
                    "flag": meta["flag"],
                    "type": typ,
                    "type_label": _TYPE_LABEL[typ],
                    "sector": sector,
                    "currency": meta["ccy"],
                    "has_options": has_opt,
                })
    return rows


_ROWS = _flatten()
_BY_SYMBOL = {r["symbol"]: r for r in _ROWS}


def meta() -> dict:
    """Counts per market/type for building the picker UI."""
    markets, types = [], []
    for mk in _MARKET_ORDER:
        count = sum(1 for r in _ROWS if r["market"] == mk)
        flag = _MARKETS[mk]["flag"]
        markets.append({"market": mk, "label": _MARKET_LABEL[mk], "flag": flag, "count": count})
    for typ in _TYPE_ORDER:
        types.append({
            "type": typ, "label": _TYPE_LABEL[typ],
            "count": sum(1 for r in _ROWS if r["type"] == typ),
        })
    return {
        "total": len(_ROWS),
        "options_enabled": sum(1 for r in _ROWS if r["has_options"]),
        "markets": markets,
        "types": types,
    }


def search(q: str = "", market: str = "", type_: str = "",
           options_only: bool = False, limit: int = 60) -> List[dict]:
    """Filter + rank the universe. Starts-with beats contains, symbol beats name."""
    qn = (q or "").strip().lower()
    out = []
    for r in _ROWS:
        if market and r["market"] != market:
            continue
        if type_ and r["type"] != type_:
            continue
        if options_only and not r["has_options"]:
            continue
        if qn:
            sym_l, name_l = r["symbol"].lower(), r["name"].lower()
            if sym_l.startswith(qn):
                rank = 0
            elif name_l.startswith(qn):
                rank = 1
            elif qn in sym_l:
                rank = 2
            elif qn in name_l:
                rank = 3
            else:
                continue
        else:
            rank = 1
        out.append((rank, r))
    out.sort(key=lambda t: (t[0], t[1]["symbol"]))
    return [r for _, r in out[: max(1, min(limit, 200))]]


def get(symbol: str) -> Optional[dict]:
    return _BY_SYMBOL.get(symbol)


def currency_of(symbol: str) -> str:
    r = _BY_SYMBOL.get(symbol)
    if r:
        return r["currency"]
    s = symbol.upper()
    if s.endswith(".NS") or s.endswith(".BO"):
        return "INR"
    if s.endswith(".L"):
        return "GBP"
    if s.endswith(".DE") or s.endswith(".AS") or s.endswith(".PA") or s.endswith(".SW") or s.endswith(".CO"):
        return "EUR"
    if s.endswith(".T"):
        return "JPY"
    return "USD"
