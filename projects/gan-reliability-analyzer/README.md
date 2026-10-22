# GaN Reliability Curve Analyzer

這是一個以**合成資料**示範的可重現小型分析專案，目的是把 p-GaN HEMT 可靠度文獻中常見的資料整理工作，轉成可以檢查、重跑、說明限制的 Python 練習。它不是 WLab 的量測資料、TCAD deck 或研究成果重現；程式不宣稱使用過 B1500A/B1505A，也不代表已具備實驗室設備操作經驗。

## 專案會做什麼

`run_analysis.py` 會讀取量測格式 CSV，對每個 `device_id × stress_time_s × temperature_C` 分組：

1. 從 transfer sweep 以定電流法抽取 `VTH`。預設門檻為 `1e-3 A`；兩個相鄰點跨越門檻時做線性內插。若曲線沒有跨越門檻，會回報 out-of-range；若出現多個 crossing 或下降段造成不唯一，會回報 non-monotonic。
2. 從 output sweep 的低場窗口（預設 `0.01–0.10 V`）以 `ID = slope × VDS + intercept` 做最小平方直線回歸，並輸出 `RON = 1 / slope`、`R²` 與使用點數。這裡的窗口與 `Vg` 是明確參數，不把任意區段稱為物理上的線性區。
3. 以每個相同元件、溫度與量測窗口條件中**唯一的 `stress_time_s=0` row**為 baseline，計算 `ΔVTH = VTH − VTH_baseline` 與 `normalized_RON = RON / RON_baseline`；不會因排序而把最小但非零的 stress time 當 baseline。
4. 若提供 failure CSV，以**完整失效樣本**做二參數 Weibull MLE。為避免把右設限資料靜默排除，`fit_weibull` 遇到任一 `event_observed=0` 會直接拒絕；預設 demo 的完整失效檔和另存的 censored example 分開。程式不做壽命外推，也不把結果解釋成實驗室的失效物理結論。
5. 產生至少四個 SVG 圖和 CSV summary。SVG 使用純 Python 寫出，因此沒有繪圖套件時仍能重跑；若日後想改成 matplotlib 圖，可依 `requirements-optional.txt` 安裝。

## 快速開始

在此資料夾執行（Windows PowerShell 範例）：

```powershell
$py = "python"
& $py .\generate_demo_data.py
& $py .\run_analysis.py --measurement-csv .\data\synthetic_measurements.csv --failure-csv .\data\failure_events.csv --output-dir .\outputs
```

輸出包括 `summary_metrics.csv`、`weibull_fit.csv`、`transfer_curves.svg`、`stress_metrics.svg`、`delta_vth_metrics.svg` 與 `weibull_probability.svg`。資料欄位為 `device_id,sweep,stress_time_s,temperature_C,Vg_V,Vds_V,Id_A,Ig_A,cycle`；`sweep=transfer` 使用單一固定 `Vds_V` 的 `Vg_V`、`Id_A`，`sweep=output` 使用固定 `Vg_V`、`Vds_V`、`Id_A`。

這份資料由固定 seed 的公式產生，README 和程式會明確標記 `synthetic`。不同設備的量測溫度、偏壓、取樣率及 compliance 應寫入自己的 metadata；目前程式不會猜測缺失的物理條件。

## 公式與判定

定電流門檻的線性內插為 `VTH = Vg0 + (Ith − Id0) (Vg1 − Vg0) / (Id1 − Id0)`。低場輸出回歸 `ID = slope·VDS + intercept`，因此 `RON = 1/slope`；若 slope 不為正或 `R²` 不可計算，該分組會停止並提示資料問題。

二參數 Weibull 對完整失效時間 `t_i > 0` 的密度為 `f(t) = (β/η)(t/η)^(β−1) exp(−(t/η)^β)`。程式用一維二分法解二參數 MLE 的 shape `β` 方程，再以 `η = (mean(t^β))^(1/β)` 計算 scale。這是教學用的 full-failure estimate；程式要求所有時間 finite、正值，且 flags 只能是 0/1；含 censored row 時會拒絕，不假裝完成 right-censored likelihood、confidence interval、加速模型或 physics-of-failure 推論。

## 學習方式與自驗問題

建議先開 `tutorial.md`，再依序執行資料產生、分析、測試。完成後應能回答：為什麼 `VTH` 門檻電流與單位必須寫清楚？若 `Id–Vg` 跨越 `Ith` 兩次為何不能默默選第一個？`RON = 1/slope` 的單位為何是 ohm？為什麼 baseline 要在每個 `device_id` 內獨立計算？這個 Weibull 結果能否直接說明 WLab 實際失效機制？合成資料 plot 可以證明什麼、不能證明什麼？

若未來加入真實資料，先保留原始檔、寫下溫度與偏壓 metadata，並在 README 註明資料授權、前處理與任何排除規則。不要把 synthetic demo 寫成已完成的實驗。

## AI-assisted attribution

本專案的程式結構、測試草稿、README 與教學文字是在 AI 協助下產生，再由人工檢閱並以 bundled Python 實際執行測試與 demo。合成資料由 `generate_demo_data.py` 的固定公式產生，不是實驗室資料；AI 協助不等於使用者已獨立完成實驗或研究。使用者在對外分享前仍需自行理解公式、重跑程式、檢查假設與改寫成自己的研究紀錄。

