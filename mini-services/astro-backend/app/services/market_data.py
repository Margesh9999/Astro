"""
Market data service using yfinance
"""
from app.core.ssl_fix import ensure_ssl_certs  # noqa: F401  (must run first)

import time
import io
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import os

logger = logging.getLogger(__name__)

# Yahoo symbol -> Stooq symbol (fallback CSV source when Yahoo blocks/rate-limits)
STOOQ_MAP = {
    "^GSPC": "^spx",
    "^IXIC": "^ndq",
    "^FTSE": "^ukx",
    "^DJI": "^dji",
    "^NSEI": "^spx",   # no Nifty on stooq - degrade to S&P proxy rather than fail
    "^BSESN": "^spx",  # no Sensex on stooq - degrade to S&P proxy rather than fail
}
PERIOD_DAYS = {
    "1d": 5, "5d": 10, "1mo": 40, "3mo": 100, "6mo": 200,
    "1y": 380, "2y": 760, "5y": 1900, "10y": 3800, "ytd": 380, "max": 12000,
}

DEMO_DATA = os.environ.get("ASTRO_DEMO_DATA", "").lower() in ("1", "true", "yes")
DEMO_START = {"^GSPC": "1927-12-30", "^DJI": "1950-01-03", "^IXIC": "1971-02-05", "^FTSE": "1984-01-03",
              "^NSEI": "2007-09-17", "^BSESN": "1997-07-01"}


def synthetic_history(symbol: str, period: str = "10y") -> pd.DataFrame:
    """Deterministic GBM price history for offline development and CI (ASTRO_DEMO_DATA=1).

    Never used unless the env flag is set, so live users always see real quotes.
    """
    seed = sum(ord(c) * (i + 1) for i, c in enumerate(symbol)) % (2 ** 32)
    rng = np.random.default_rng(seed)
    start = pd.Timestamp(DEMO_START.get(symbol, "1995-01-03"))
    idx = pd.bdate_range(start, pd.Timestamp.today().normalize())
    n = len(idx)
    vol = 0.011 * np.exp(0.35 * np.sin(np.arange(n) / 600.0))
    rets = 0.0003 + vol * rng.standard_t(5, n) / np.sqrt(5 / 3)
    close = 100.0 * np.exp(np.cumsum(rets))
    open_ = close * (1 + rng.normal(0, 0.002, n))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.004, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.004, n)))
    df = pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close,
                       "Volume": rng.integers(1_000_000, 5_000_000, n).astype(float)}, index=idx)
    df.index.name = "Date"
    if period != "max":
        df = df.iloc[-min(n, int(PERIOD_DAYS.get(period, 3800) * 252 / 365) + 1):].copy()
    df["Returns"] = df["Close"].pct_change()
    df["Log_Returns"] = np.log(df["Close"] / df["Close"].shift(1))
    return df


class MarketDataService:
    """Service for fetching and processing market data"""

    def __init__(self, cache_dir: str = "./data"):
        """
        Initialize market data service

        Args:
            cache_dir: Directory for caching data
        """
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        # In-memory TTL caches (survives within the uvicorn worker process)
        #   _hist_cache:  key -> (dataframe, fetched_at)   TTL 15 min
        #   _info_cache:  symbol -> (info dict, fetched_at) TTL 6 h
        self._hist_cache: Dict[str, Tuple[pd.DataFrame, float]] = {}
        self._info_cache: Dict[str, Tuple[Dict, float]] = {}
        self.HIST_TTL = 15 * 60
        self.INFO_TTL = 6 * 60 * 60
        ensure_ssl_certs()
        logger.info(f"MarketDataService initialized with cache dir: {cache_dir}")

    # ------------------------------------------------------------------
    # Fallback source: Stooq free daily CSV (no auth, generous limits)
    # ------------------------------------------------------------------
    def _stooq_history(self, symbol: str, period: str = "10y") -> pd.DataFrame:
        """Fetch daily OHLCV from stooq.com as a Yahoo fallback."""
        sq = STOOQ_MAP.get(symbol, symbol.lower().replace("^", ""))
        days = PERIOD_DAYS.get(period, 380)
        d2 = datetime.utcnow().date()
        d1 = d2 - timedelta(days=days)
        url = (
            f"https://stooq.com/q/d/l/?s={sq}&i=d"
            f"&d1={d1.strftime('%Y%m%d')}&d2={d2.strftime('%Y%m%d')}"
        )
        try:
            resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            if "No data" in resp.text[:200] or len(resp.text) < 60:
                return pd.DataFrame()
            df = pd.read_csv(io.StringIO(resp.text))
            if df.empty or "Close" not in df.columns:
                return pd.DataFrame()
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.set_index("Date").sort_index()
            df = df[[c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]]
            for c in ["Open", "High", "Low", "Close", "Volume"]:
                if c not in df.columns:
                    df[c] = 0.0
            df.index = df.index.tz_localize("UTC")
            logger.warning(f"Stooq fallback served {len(df)} rows for {symbol} ({period})")
            return df.tail(days)
        except Exception as exc:
            logger.error(f"Stooq fallback failed for {symbol}: {exc}")
            return pd.DataFrame()

    def _cache_get(self, key: str) -> Tuple[Optional[pd.DataFrame], bool]:
        """Return (cached_df, is_stale_but_usable) for a history key."""
        entry = self._hist_cache.get(key)
        if not entry:
            return None, False
        df, ts = entry
        fresh = (time.time() - ts) < self.HIST_TTL
        return df, not fresh

    def fetch_historical_data(
        self,
        symbol: str,
        period: str = "10y",
        interval: str = "1d"
    ) -> pd.DataFrame:
        """
        Fetch historical market data

        Args:
            symbol: Stock symbol (e.g., 'AAPL', '^GSPC')
            period: Data period ('1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max')
            interval: Data interval ('1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h', '1d', '5d', '1wk', '1mo', '3mo')

        Returns:
            DataFrame with OHLCV data
        """
        key = f"{symbol}|{period}|{interval}"
        if DEMO_DATA:
            return synthetic_history(symbol, period)
        cached, stale = self._cache_get(key)
        if cached is not None and not stale:
            return cached

        try:
            logger.info(f"Fetching data for {symbol} - period: {period}, interval: {interval}")
            ticker = yf.Ticker(symbol)
            data = ticker.history(period=period, interval=interval)

            if data.empty:
                logger.warning(f"No data returned for {symbol}")
                data = self._stooq_history(symbol, period)
                if data.empty and cached is not None:
                    logger.warning(f"Serving stale cache for {key}")
                    return cached
                if not data.empty:
                    data["Returns"] = data["Close"].pct_change()
                    data["Log_Returns"] = np.log(data["Close"] / data["Close"].shift(1))
                    self._hist_cache[key] = (data, time.time())
                return data

            # Ensure we have the expected columns
            required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            if not all(col in data.columns for col in required_columns):
                logger.warning(f"Missing expected columns for {symbol}. Got: {data.columns.tolist()}")
                return pd.DataFrame()

            # Add returns calculation
            data['Returns'] = data['Close'].pct_change()
            data['Log_Returns'] = np.log(data['Close'] / data['Close'].shift(1))

            # Drop rows whose Close is NaN (Yahoo emits a partial last row
            # while the session is live; NaN would poison JSON + sklearn)
            data = data[data['Close'].notna()]

            self._hist_cache[key] = (data.copy(), time.time())
            logger.info(f"Successfully fetched {len(data)} rows for {symbol}")
            return data

        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            fallback = self._stooq_history(symbol, period)
            if not fallback.empty:
                fallback["Returns"] = fallback["Close"].pct_change()
                fallback["Log_Returns"] = np.log(fallback["Close"] / fallback["Close"].shift(1))
                self._hist_cache[key] = (fallback.copy(), time.time())
                return fallback
            if cached is not None:
                logger.warning(f"Yahoo+Stooq failed for {symbol}; serving stale cache")
                return cached
            return pd.DataFrame()

    def fetch_multiple_symbols(
        self,
        symbols: List[str],
        period: str = "10y",
        interval: str = "1d"
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch historical data for multiple symbols

        Args:
            symbols: List of stock symbols
            period: Data period
            interval: Data interval

        Returns:
            Dictionary mapping symbols to DataFrames
        """
        results = {}
        for symbol in symbols:
            data = self.fetch_historical_data(symbol, period, interval)
            if not data.empty:
                results[symbol] = data
            else:
                logger.warning(f"No data fetched for {symbol}")

        return results

    def get_real_time_price(self, symbol: str) -> Optional[float]:
        """
        Get current real-time price for a symbol

        Args:
            symbol: Stock symbol

        Returns:
            Current price or None if error
        """
        if DEMO_DATA:
            return float(synthetic_history(symbol, "1mo")["Close"].iloc[-1])
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="1d", interval="1m")
            if not data.empty:
                return float(data['Close'].iloc[-1])
            # Stooq intraday-less quote fallback
            sq = STOOQ_MAP.get(symbol, symbol.lower().replace("^", ""))
            resp = requests.get(
                f"https://stooq.com/q/l/?s={sq}&f=sd2t2ohlcv&h&e=csv",
                timeout=10, headers={"User-Agent": "Mozilla/5.0"},
            )
            if resp.ok and "No data" not in resp.text[:100]:
                row = pd.read_csv(io.StringIO(resp.text))
                if not row.empty and "Close" in row.columns:
                    val = float(row["Close"].iloc[0])
                    if val > 0:
                        return val
            return None
        except Exception as e:
            logger.error(f"Error getting real-time price for {symbol}: {e}")
            return None

    def get_symbol_info(self, symbol: str) -> Dict:
        """
        Get basic information about a symbol

        Args:
            symbol: Stock symbol

        Returns:
            Dictionary with symbol information
        """
        cached = self._info_cache.get(symbol)
        if cached and (time.time() - cached[1]) < self.INFO_TTL:
            return cached[0]
        try:
            if DEMO_DATA:
                raise RuntimeError("demo data mode")
            ticker = yf.Ticker(symbol)
            info = ticker.info
            result = {
                'symbol': symbol,
                'name': info.get('longName', 'N/A'),
                'sector': info.get('sector', 'N/A'),
                'industry': info.get('industry', 'N/A'),
                'market_cap': info.get('marketCap', 0),
                'currency': info.get('currency', 'USD')
            }
            self._info_cache[symbol] = (result, time.time())
            return result
        except Exception as e:
            logger.error(f"Error getting info for {symbol}: {e}")
            if cached:
                return cached[0]
            NAMES = {"^GSPC": "S&P 500", "^IXIC": "NASDAQ Composite", "^NSEI": "Nifty 50",
                     "^BSESN": "BSE Sensex", "^FTSE": "FTSE 100"}
            return {'symbol': symbol, 'name': NAMES.get(symbol, symbol),
                    'sector': 'Index', 'industry': 'Index', 'market_cap': 0, 'currency': 'USD'}

    def cache_data(self, data: pd.DataFrame, filename: str) -> str:
        """
        Cache data to disk

        Args:
            data: DataFrame to cache
            filename: Name of file (without extension)

        Returns:
            Path to cached file
        """
        try:
            filepath = os.path.join(self.cache_dir, f"{filename}.pkl")
            data.to_pickle(filepath)
            logger.info(f"Data cached to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error caching data: {e}")
            return ""

    def load_cached_data(self, filename: str) -> Optional[pd.DataFrame]:
        """
        Load cached data from disk

        Args:
            filename: Name of file (without extension)

        Returns:
            DataFrame or None if not found/error
        """
        try:
            filepath = os.path.join(self.cache_dir, f"{filename}.pkl")
            if os.path.exists(filepath):
                data = pd.read_pickle(filepath)
                logger.info(f"Data loaded from {filepath}")
                return data
            else:
                logger.warning(f"No cached data found at {filepath}")
                return None
        except Exception as e:
            logger.error(f"Error loading cached data: {e}")
            return None

    def prepare_features_target(
        self,
        market_data: pd.DataFrame,
        target_column: str = 'Returns',
        lookback_periods: int = 5
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prepare features and target for machine learning

        Args:
            market_data: DataFrame with market data and returns
            target_column: Column to use as target
            lookback_periods: Number of past periods to use as features

        Returns:
            Tuple of (features, target) arrays
        """
        try:
            # Create lagged features
            df = market_data.copy()

            # Add lagged returns as features
            for i in range(1, lookback_periods + 1):
                df[f'Returns_Lag_{i}'] = df[target_column].shift(i)

            # Add lagged volume
            df['Volume_Lag_1'] = df['Volume'].shift(1)
            df['Volume_Change'] = df['Volume'].pct_change()

            # Add price-based features
            df['High_Low_Ratio'] = df['High'] / df['Low']
            df['Close_Open_Ratio'] = df['Close'] / df['Open']

            # Drop NaN values
            df = df.dropna()

            if len(df) == 0:
                logger.warning("No data remaining after feature creation")
                return np.array([]), np.array([])

            # Select feature columns
            feature_cols = [col for col in df.columns if col not in [target_column, 'Open', 'High', 'Low', 'Close', 'Volume']]
            X = df[feature_cols].values
            y = df[target_column].values

            logger.info(f"Prepared features: {X.shape[1]} features, {len(X)} samples")
            return X, y

        except Exception as e:
            logger.error(f"Error preparing features and target: {e}")
            return np.array([]), np.array([])