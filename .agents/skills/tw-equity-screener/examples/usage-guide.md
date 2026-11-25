# tw-equity-screener 使用指南

給使用者看的操作說明，不是 agent 指令；流程規則以 `../SKILL.md` 為準。

## 指令一覽

| 情境 | 指令 | 什麼時候用 |
|---|---|---|
| 第一次 | `/tw-equity-screener --backfill` | 第一次手動跑，建議在週六 |
| 每週例行 | `/tw-equity-screener` | 每週六以後執行一次，或交給排程 |
| 重跑過去某天 | `/tw-equity-screener --asof YYYY-MM-DD` | 只限之前跑過、有快取的日期 |
| 加板塊研究 | `/tw-equity-screener --deep-research sector` | 想看強勢產業的景氣循環時 |
| 加個股研究 | `/tw-equity-screener --deep-research finalists` | 想先研究 Tier A 前 3 名時 |

三個參數可以一起用，例如 `--backfill --deep-research sector`。`--deep-research` 只能填 `off`、`sector`、`finalists`，預設是 `off`。

## 第一次使用

- 一定要加 `--backfill`。第一次沒有任何快取，要抓約 270 個交易日的資料，大約 770 次請求，至少 40 分鐘。沒加的話會以 exit 5 停下，問你要不要補抓。
- 開始前先確認 `index.html` 和 `README.md` 沒有改到一半、還沒提交的內容；有的話會停下。Step 6 會把這兩個檔整份提交。
- Step 6 會 commit 再 push，push 會一起送出本地所有還沒推的 commit。
- 第一週沒有上一週可以比較，所以新進、退出都是空的。第二週開始才有變化可看。

## 排程使用

- 排程執行 `/tw-equity-screener`，不帶任何參數，`asof` 會自動取最近一個資料已公布的交易日，通常是週五。
- 排程用 `windows-task-scheduler` skill 註冊，任務名稱是 `Agent-TaskHtml-TwScreener-claude`，每週日 05:00 開互動視窗執行。push 前的確認和權限詢問都會在那個視窗等你回答。
- 那天電腦沒開的話，下次登入時會補跑。
- 想讓每週都附帶 deep research，要改排程的 CliArgs。每次都很耗 token，不建議。
- 暫停或恢復排程：

  ```powershell
  Disable-ScheduledTask -TaskName "Agent-TaskHtml-TwScreener-claude"
  Enable-ScheduledTask  -TaskName "Agent-TaskHtml-TwScreener-claude"
  ```

## 特殊狀況

| 狀況 | 結果 | 怎麼處理 |
|---|---|---|
| 週五下午或晚上就跑 | exit 3，部分資料表還沒公布 | 週六以後再跑 |
| FinMind 額度用完 | exit 2 | 一小時內會重置，重跑會從快取接著抓 |
| 中斷約 6 週（缺 30 個以上交易日） | exit 5 | 確認後加 `--backfill` 重跑 |
| 同一週重跑 | 整個週資料夾會被替換 | 結果一樣；但 `review.json` 和研究檔會被刪掉，有研究檔要先移到別處 |
| `--asof` 指定沒快取過的日期 | exit 4 | 改成跑過的日期，或拿掉 `--asof` |
| 用 `--asof` 重跑舊的一週 | 首頁卡片和 README 會改指向那一週（已知問題 M3） | 之後再跑一次最新一週，就會改回來 |
| 整週沒有交易（例如春節） | `asof` 落在上一週，等於重跑上週 | 沒有壞處；同樣會清掉上週的 review 和研究檔 |
| 檢查不變量失敗 | exit 1，不會寫入週資料夾 | 看輸出的訊息，回報問題 |
| push 被拒絕 | 停下回報，不會強制推送 | 先 pull 或處理衝突，再手動推 |

## 要不要帶 deep research

一般建議用 `off`，有需要再開：

1. 它不會讓篩選結果更好。分數、排名、分級全由腳本計算，deep research 只會在週資料夾裡多寫研究檔（`sector_research.md` 或 `research_{code}.md`），不會改變哪些股票上榜。
2. 成本很高。每一次都是長時間、大量 token 的多 agent 研究。重跑同一週時，研究檔也會被刪掉。
3. `/tw-equity-report <code>` 本來就會針對那一檔跑 deep research。`finalists` 只是把這一步提前，研究檔放在週資料夾，之後寫報告可以直接沿用，總成本差不多。

建議流程：先用 `off` 跑完，看 Tier A 名單，再對有興趣的個股跑 `/tw-equity-report <code>`。想看產業循環時，再用 `--deep-research sector` 重跑那一週，重跑走快取，只要幾分鐘。
