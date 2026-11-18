import pandas as pd

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ["open", "high", "low", "close", "volume"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["close"]).reset_index(drop=True)
    out["ema9"] = out["close"].ewm(span=9, adjust=False).mean()
    out["ema21"] = out["close"].ewm(span=21, adjust=False).mean()
    delta = out["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, pd.NA)
    out["rsi14"] = 100 - (100 / (1 + rs))
    typical = (out["high"] + out["low"] + out["close"]) / 3
    pv = typical * out["volume"]
    if "datetime" in out.columns:
        dates = pd.to_datetime(out["datetime"], errors="coerce").dt.date
        out["vwap"] = pv.groupby(dates).cumsum() / out["volume"].groupby(dates).cumsum().replace(0, pd.NA)
    else:
        out["vwap"] = pv.cumsum() / out["volume"].cumsum().replace(0, pd.NA)
    return out

def make_signal(row) -> str:
    vals = [row.get("ema9"), row.get("ema21"), row.get("rsi14"), row.get("vwap")]
    if any(pd.isna(v) for v in vals):
        return "WAIT"
    # Conservative rule-based confirmation; AI layer is intentionally not allowed
    # to override risk controls or submit orders.
    if row["ema9"] > row["ema21"] and 52 <= row["rsi14"] <= 68 and row["close"] > row["vwap"]:
        return "BUY"
    if row["ema9"] < row["ema21"] and 32 <= row["rsi14"] <= 48 and row["close"] < row["vwap"]:
        return "SELL"
    return "WAIT"
