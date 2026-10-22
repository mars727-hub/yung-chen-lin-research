# p-GaN HEMT 可靠度選讀與學習問題

更新2026/10/22。這是公開文獻整理與個人選讀安排，由AI協助整理，不代表個人已完成精讀、實驗或論文重現。未使用GitHub課堂筆記。

## 1. 反向導通與閘極失效（2024）

Toward Understanding the Failure Mechanism in p-GaN Gate HEMTs Operating in Reverse Conduction Diode Mode

- 來源層級：公開 accepted manuscript
- 問題：第三象限下的 gate leakage 與失效位置，如何由電性、TCAD 與 EMMI 交叉判斷？
- 方法與範圍：公開作者稿結合反向偏壓量測、場分布模擬與發光位置觀察。閱讀重點是端點定義、compliance、掃描條件與證據鏈。
- 預計交付：整理一張應力→曲線→模擬→位置證據圖，列出熱與接觸效應等替代解釋。
- [DOI](https://doi.org/10.1109/TED.2024.3412095)｜[原始來源](https://biblio.ugent.be/publication/01JD55KQR23BND1QH5FWMHB85X)

## 2. p-GaN 閘極時間相依崩潰（2022）

High Threshold Voltage Enhancement-Mode Regrown p-GaN Gate HEMTs With a Robust Forward Time-Dependent Gate Breakdown Stability

- 來源層級：官方機構摘要
- 問題：高 VTH 與 forward TDGB 穩定度如何一起評估？
- 方法與範圍：摘要比較不同 AlGaN barrier 的 regrown p-GaN 元件。完整 stress protocol、樣本數與外推模型尚需全文確認。
- 預計交付：先區分 VTH、gate breakdown、失效分布與壽命外推所需的證據，不從摘要重建未公開條件。
- [DOI](https://doi.org/10.1109/LED.2022.3198876)｜[原始來源](https://biblio.ugent.be/publication/01GP3NCJFGMP9VW411PDCFC0HH)

## 3. 連續切換下的 SBD 劣化（2026）

Analysis of Trap-Induced Dynamic Degradation in AlGaN/GaN Gated-Edge Termination Schottky Barrier Diodes Under Continuous Switching Operation

- 來源層級：正式書目，全文待取得
- 問題：連續切換時，應如何定義 stress 與 dynamic parameter 的讀取窗口？
- 方法與範圍：目前僅以 WLab 出版清單確認題名與 DOI；方法、條件和數值結果未核實，不引用未讀全文的細節。
- 預計交付：取得合法全文後，補上切換電路、時間窗、量測條件與失效判準。
- [DOI](https://doi.org/10.1109/TED.2026.3714751)｜[原始來源](https://tianliwu.wixsite.com/nycuwlab/publications)

## 4. U-Net 與 TCAD 電勢圖（2024）

Using U-Net Convolutional Neural Network to Model Pixel-Based Electrostatic Potential Distributions in GaN Power MIS-HEMTs

- 來源層級：出版社開放全文
- 問題：用 surrogate model 加速模擬時，如何驗證未見結構與偏壓的泛化？
- 方法與範圍：將 TCAD 元件與偏壓資訊編碼後，用 U-Net 預測二維電勢。閱讀重點是輸入表示、訓練／驗證分割與誤差定義。
- 預計交付：畫出 input encoding→model→potential map 流程，列出分割方式與分布外預測的限制，不宣稱取得原始 dataset 或重現。
- [DOI](https://doi.org/10.1038/s41598-024-58112-9)｜[原始來源](https://www.nature.com/articles/s41598-024-58112-9)

## 5. IGZO TFT 與 GaN 三維整合（2025）

Demonstration of TFTs 3D Monolithically Integrated on GaN HEMTs Using Cascode Configuration With High Breakdown Voltage (>1900 V)

- 來源層級：出版社開放全文
- 問題：製程、通道厚度與 cascode 電壓分配如何反映在曲線上？
- 方法與範圍：由公開製程流程與電性圖，對照 TFT、GaN HEMT 及 cascode 的參數定義；區分元件特性與整合後的結果。
- 預計交付：重畫簡化製程圖，逐步連結電性與可能的介面／漏電問題。
- [DOI](https://doi.org/10.1038/s41598-025-23825-y)｜[原始來源](https://www.nature.com/articles/s41598-025-23825-y)

## 6. dynamic RON 與 VTH 的量測（2024）

Dynamic On-Resistance and Threshold Voltage Instability Evaluation Circuit for Power GaN HEMTs Devices

- 來源層級：校方出版摘要
- 問題：如何在相同 switching condition 下比較 RON 與 VTH instability？
- 方法與範圍：官方摘要介紹同一硬切換條件下評估兩者的電路。完整 topology、timing 與誤差須取得全文後核對。
- 預計交付：整理 baseline→stress→delay→readout→recovery 時間線，標出每項參數的抽取時點。
- [DOI](https://doi.org/10.1109/TIE.2023.3332998)｜[原始來源](https://scholar.nycu.edu.tw/zh/publications/dynamic-on-resistance-and-threshold-voltage-instability-evaluatio/)

## 計畫與教學來源

- [GRB 19508397](https://www.grb.gov.tw/search/planDetail?id=19508397)：p-GaN split-gate／embedded-SBD可靠度計畫，2026–2029。計畫不是第七篇論文，也不是加入實驗室的證明。
- [WLab官方網站](https://tianliwu.wixsite.com/nycuwlab)與[Teaching](https://tianliwu.wixsite.com/nycuwlab/teaching)：研究與學習入口。
- [電子所教師頁](https://iee.nycu.edu.tw/en/teacher/p1.php?num=225&page=1)：研究方向與聯絡資料。

每篇個人紀錄需另外寫下實際閱讀日期、來源段落、自己的解釋與尚待驗證的問題。官方摘要與書目不能補造全文方法。
