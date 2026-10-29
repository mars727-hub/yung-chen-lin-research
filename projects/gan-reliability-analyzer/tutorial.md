# 分段教學

## 1. 產生資料

`generate_demo_data.py` 產生 `data/synthetic_measurements.csv`、預設全失效的 `data/failure_events.csv`，以及故意含右設限列的 `data/failure_events_censored_example.csv`。資料是固定公式與固定 seed 的 educational synthetic data，不包含 WLab 未公開資料。

## 2. 重跑分析

```powershell
$py = "python"
& $py .\run_analysis.py --measurement-csv .\data\synthetic_measurements.csv --failure-csv .\data\failure_events.csv --output-dir .\outputs
```

先看 `summary_metrics.csv` 的 `vth_V`、`ron_ohm`、`delta_vth_V` 和 `normalized_ron`，再看 SVG。注意每個相同元件、溫度與量測窗口條件都必須有唯一的 stress time `0` baseline；程式不會因排序而任選第一筆。normalized RON 只是相對於 baseline 的資料整理欄位。

## 3. 修改一個分析假設

把 `--current-threshold-a 1e-3` 改成 `8e-4`，比較 `VTH` 是否改變；把 `--ron-vds-max-v 0.05` 改成 `0.10`，比較 RON 和 R²。把這些改動寫入研究筆記，說明窗口並非自然常數。

若把 `--failure-csv .\data\failure_events_censored_example.csv` 傳給 CLI，程式會明確拒絕，因為此版本尚未實作 right-censored likelihood；不要把 censored row 靜默刪除後稱為可靠度估計。

## 4. 面談時可如何描述

可以說：「我做了一個使用固定合成資料的教學型 analyzer，練習把 transfer/output sweep 的欄位驗證、VTH 內插、低場 RON 回歸、stress shift 與簡化 Weibull MLE 串起來。我知道這不是實際量測，也沒有宣稱重現老師的 TCAD 或 reliability experiment；如果加入實驗室，我希望先依照 SOP 學習真實資料的 metadata、量測流程與品質檢查。」

不要說「我已完成 GaN reliability experiment」、「我已使用 WLab 儀器」或「我重現了論文結果」。

