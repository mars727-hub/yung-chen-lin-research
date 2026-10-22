# 林勇辰的研究學習履歷

面向大學部專題申請的靜態網站，包含真實工程背景、公開非筆記專案、研究選讀、合成曲線互動分析與學習計畫。

網站：https://mars727-hub.github.io/yung-chen-lin-research/

## 本機預覽

無建置工具或前端依賴。在此目錄執行 `python -m http.server 4173 --bind 127.0.0.1`，開啟 http://127.0.0.1:4173/ 。需要HTTP以載入JSON與CSV；不要直接用file://。

## 更新內容

- `index.html`：履歷與研究敘事。
- `data/portfolio.json`：六篇選讀、公開專案、規劃檢核。`updated`為實際人工更新日期，不自動生成學習進度。
- `research/study-plan.md`：完整公開學習安排。
- `downloads/resume.html`：可列印履歷，未包含私人電話。
- `projects/gan-reliability-analyzer/`：AI協助的Python教學原型、合成CSV與測試。
- `assets/app.js`：互動頁的定電流VTH、低場RON與baseline比較；設定改變後即重新計算，可下載帶條件欄位的結果。

將個人工作列為完成前，須有實際閱讀或操作紀錄與可出示證據。GitHub Pages不會執行Python；瀏覽器僅用內建合成CSV計算。這個網站不傳送訪客輸入，無追蹤、登入或後端資料庫。

## 內容範圍

不引用或連結GitHub上的課堂筆記。舊專案僅連結已核實的公開成果；未完成的風電爬蟲不列為完成作品。引用研究均附原始來源與存取層級，沒有實驗室未公開資料，也不宣稱已加入WLab、操作設備或重現論文。

網站、研究整理與分析原型由AI協助製作，個人實作與理解須本人持續驗證。工作改善百分比依本人提供履歷；不延伸為成本、整體工期或檢測準確率。這是個人研究學習履歷，非WLab官方網站。

## 發布

GitHub Pages以main分支根目錄發布，`.nojekyll`保持純靜態。每次更新後應檢查桌面與手機版、互動輸出與下載連結。測試與發布驗證的本機工作檔存於未發布的`_authoring/`。
