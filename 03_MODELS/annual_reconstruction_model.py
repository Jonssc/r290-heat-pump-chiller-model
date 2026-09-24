"""Pure annual load reconstruction helpers. No file I/O and no plotting."""
from __future__ import annotations
import numpy as np
import pandas as pd


def hampel_filter(series, window_samples=13, mad_factor=4.0, minimum_absolute_spike=10.0):
    values = pd.to_numeric(series, errors="coerce").astype(float)
    min_periods = max(5, int(window_samples) // 2)
    local_median = values.rolling(window=int(window_samples), center=True, min_periods=min_periods).median()
    absolute_deviation = (values - local_median).abs()
    local_mad = absolute_deviation.rolling(window=int(window_samples), center=True, min_periods=min_periods).median()
    robust_sigma = 1.4826 * local_mad
    spike = (absolute_deviation > float(mad_factor) * robust_sigma) & (absolute_deviation > float(minimum_absolute_spike))
    spike = spike | ((robust_sigma == 0) & (absolute_deviation > float(minimum_absolute_spike)))
    return values.mask(spike), spike.fillna(False)


def classify_ventilation_mode(setpoint_C, heating_min_C=30.0, cooling_max_C=15.0):
    setpoint = pd.to_numeric(setpoint_C, errors="coerce")
    mode = pd.Series("Transition / unknown", index=setpoint.index, dtype="object")
    mode.loc[setpoint >= float(heating_min_C)] = "Heating"
    mode.loc[setpoint <= float(cooling_max_C)] = "Cooling"
    return mode


def allocate_ventilation_power(branch_power_kW, ventilation_mode):
    branch = pd.to_numeric(branch_power_kW, errors="coerce")
    heating = pd.Series(np.nan, index=branch.index, dtype=float)
    cooling = pd.Series(np.nan, index=branch.index, dtype=float)
    valid = branch.notna()
    mh = valid & ventilation_mode.eq("Heating")
    mc = valid & ventilation_mode.eq("Cooling")
    heating.loc[mh] = branch.loc[mh]
    cooling.loc[mh] = 0.0
    cooling.loc[mc] = branch.loc[mc]
    heating.loc[mc] = 0.0
    return heating, cooling


def fit_outdoor_trend(dataframe, outdoor_column, power_column, bin_width_C=1.0, minimum_bin_samples=12, rolling_bins=5):
    data = dataframe[[outdoor_column, power_column]].copy()
    data[outdoor_column] = pd.to_numeric(data[outdoor_column], errors="coerce")
    data[power_column] = pd.to_numeric(data[power_column], errors="coerce")
    data = data.dropna()
    if data.empty:
        return pd.DataFrame()
    data["outdoor_bin_C"] = np.floor(data[outdoor_column] / float(bin_width_C) + 0.5) * float(bin_width_C)
    stats = data.groupby("outdoor_bin_C")[power_column].agg(
        sample_count="count", minimum_kW="min", mean_kW="mean", median_kW="median", maximum_kW="max"
    ).reset_index().sort_values("outdoor_bin_C")
    stats["median_for_trend_kW"] = stats["median_kW"].where(stats["sample_count"] >= int(minimum_bin_samples))
    stats["trend_kW"] = stats["median_for_trend_kW"].rolling(int(rolling_bins), center=True, min_periods=2).median()
    return stats


def interpolate_trend(outdoor_C, trend_table):
    values = np.asarray(outdoor_C, dtype=float)
    result = np.full(values.shape, np.nan, dtype=float)
    if trend_table is None or trend_table.empty:
        return result
    valid = trend_table.dropna(subset=["outdoor_bin_C", "trend_kW"])
    if len(valid) < 2:
        return result
    x = valid["outdoor_bin_C"].to_numpy(float)
    y = valid["trend_kW"].to_numpy(float)
    finite = np.isfinite(values)
    if finite.any():
        result[finite] = np.interp(np.clip(values[finite], x.min(), x.max()), x, y)
    return result


def schedule_class(timestamps):
    ts = pd.to_datetime(timestamps, errors="coerce")
    return pd.DataFrame({"day_type": np.where(ts.dt.dayofweek < 5, "weekday", "weekend"), "hour": ts.dt.hour}, index=timestamps.index)


def fit_schedule_factors(dataframe, measured_power_column, base_prediction_column, timestamp_column="timestamp", minimum_samples=12):
    data = dataframe[[timestamp_column, measured_power_column, base_prediction_column]].copy()
    data[measured_power_column] = pd.to_numeric(data[measured_power_column], errors="coerce")
    data[base_prediction_column] = pd.to_numeric(data[base_prediction_column], errors="coerce")
    data = data.dropna()
    data = data[data[base_prediction_column] > 0.1]
    if data.empty:
        return pd.DataFrame(columns=["day_type", "hour", "sample_count", "factor"])
    sc = schedule_class(data[timestamp_column])
    data["day_type"] = sc["day_type"]
    data["hour"] = sc["hour"]
    data["ratio"] = data[measured_power_column] / data[base_prediction_column]
    factors = data.groupby(["day_type", "hour"])["ratio"].agg(sample_count="count", factor="median").reset_index()
    overall = float(data["ratio"].median()) if np.isfinite(data["ratio"].median()) else 1.0
    factors.loc[factors["sample_count"] < int(minimum_samples), "factor"] = np.nan
    factors["factor"] = factors["factor"].fillna(overall).clip(0.20, 5.00)
    return factors


def apply_schedule_factors(timestamps, base_prediction, factors):
    prediction = np.asarray(base_prediction, dtype=float).copy()
    if factors is None or factors.empty:
        return prediction
    sc = schedule_class(timestamps)
    lookup = {(str(r.day_type), int(r.hour)): float(r.factor) for r in factors.itertuples() if np.isfinite(float(r.factor))}
    multipliers = np.array([lookup.get((str(r.day_type), int(r.hour)), 1.0) for r in sc.itertuples(index=False)], dtype=float)
    return prediction * multipliers


def regression_metrics(actual, predicted):
    actual = np.asarray(actual, dtype=float); predicted = np.asarray(predicted, dtype=float)
    valid = np.isfinite(actual) & np.isfinite(predicted)
    actual = actual[valid]; predicted = predicted[valid]
    if len(actual) == 0:
        return {"sample_count": 0, "mean_actual_kW": np.nan, "MAE_kW": np.nan, "RMSE_kW": np.nan, "R2": np.nan}
    residual = actual - predicted
    ss_res = float(np.sum(residual**2)); ss_tot = float(np.sum((actual - np.mean(actual))**2))
    return {"sample_count": len(actual), "mean_actual_kW": float(np.mean(actual)), "MAE_kW": float(np.mean(np.abs(residual))), "RMSE_kW": float(np.sqrt(np.mean(residual**2))), "R2": 1.0 - ss_res/ss_tot if ss_tot > 0 else np.nan}

# ============================================================
# 7. VALIDATED ANNUAL-RECONSTRUCTION METHOD
#    (ported from 10_annual_plant_view_reconstructed.py)
# ============================================================

def component_hampel_filter(series, window=13, mad_factor=4.0, min_abs=10.0):
    x=pd.to_numeric(series,errors='coerce').copy();mp=max(3,int(window)//3);med=x.rolling(window,center=True,min_periods=mp).median();dev=(x-med).abs();mad=dev.rolling(window,center=True,min_periods=mp).median();sigma=1.4826*mad;threshold=np.maximum(float(mad_factor)*sigma,float(min_abs));spike=dev>threshold;return x.mask(spike),spike.fillna(False)

def fit_component_trend(data,value_col,required_mode=None,min_bin_samples=12,rolling_bins=5):
    cols=['Outdoor_C',value_col]+(['Ventilation_mode'] if required_mode is not None else []);q=data[cols].copy()
    if required_mode is not None:q=q[q.Ventilation_mode==required_mode]
    q=q.dropna(subset=['Outdoor_C',value_col]);q['Outdoor_bin_C']=np.rint(q.Outdoor_C).astype(int);bins=q.groupby('Outdoor_bin_C')[value_col].agg(sample_count='count',median_kW='median',mean_kW='mean').reset_index().sort_values('Outdoor_bin_C');bins.loc[bins.sample_count<int(min_bin_samples),'median_kW']=np.nan;bins['trend_kW']=bins.median_kW.rolling(int(rolling_bins),center=True,min_periods=1).median();valid=bins.dropna(subset=['trend_kW'])
    if len(valid)<2:raise RuntimeError(f'Insufficient data to fit {value_col}.')
    return bins,valid.Outdoor_bin_C.to_numpy(float),valid.trend_kW.to_numpy(float)

def interpolate_component_trend(temperature_C,x,y):
    return np.interp(np.asarray(temperature_C,float),x,y,left=y[0],right=y[-1])

def build_base_total_predictions(data,trend_models):
    outdoor=data.Outdoor_C.to_numpy(float);p404=interpolate_component_trend(outdoor,*trend_models['OE404_heating']);ph=np.where(data.Ventilation_mode.eq('Heating').to_numpy(),interpolate_component_trend(outdoor,*trend_models['ventilation_heating']),0.0);pc=np.where(data.Ventilation_mode.eq('Cooling').to_numpy(),interpolate_component_trend(outdoor,*trend_models['ventilation_cooling']),0.0);return np.clip(p404+ph,0,None),np.clip(pc,0,None)

def fit_total_schedule_factors(data,base_heating,base_cooling):
    w=data[['weekend','hour','Heating_load_filtered_kW','Cooling_load_filtered_kW']].copy();w['base_heating']=base_heating;w['base_cooling']=base_cooling;factors={}
    for mode in ['heating','cooling']:
        actual='Heating_load_filtered_kW' if mode=='heating' else 'Cooling_load_filtered_kW';base='base_heating' if mode=='heating' else 'base_cooling';q=w[w[actual].notna()&(w[actual]>=5.0)&(w[base]>=1.0)].copy();q['ratio']=q[actual]/q[base];factors[mode]=q.groupby(['weekend','hour']).ratio.median().clip(.30,2.00)
    return factors

def apply_total_schedule_factors(data,base_heating,base_cooling,factors):
    h=np.asarray(base_heating,float).copy();co=np.asarray(base_cooling,float).copy();weekend=data.weekend.to_numpy(int);hour=data.hour.to_numpy(int)
    for i in range(len(data)):
        key=(int(weekend[i]),int(hour[i]));h[i]*=float(factors['heating'].get(key,1.0));co[i]*=float(factors['cooling'].get(key,1.0))
    return np.clip(h,0,None),np.clip(co,0,None)

def active_fit_metrics(actual,predicted,minimum_active_load=5.0):
    y=pd.to_numeric(actual,errors='coerce').to_numpy(float);p=np.asarray(predicted,float);valid=np.isfinite(y)&np.isfinite(p)&(y>=minimum_active_load);y=y[valid];p=p[valid]
    if len(y)<2:return {'sample_count':len(y),'mean_actual_kW':np.nan,'MAE_kW':np.nan,'RMSE_kW':np.nan,'R2':np.nan}
    mae=float(np.mean(np.abs(y-p)));rmse=float(np.sqrt(np.mean((y-p)**2)));den=float(np.sum((y-np.mean(y))**2));r2=1-float(np.sum((y-p)**2))/den if den>0 else np.nan;return {'sample_count':len(y),'mean_actual_kW':float(np.mean(y)),'MAE_kW':mae,'RMSE_kW':rmse,'R2':r2}
