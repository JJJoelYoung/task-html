# Task HTML

A curated, zero-build repository of standalone HTML research deliverables, interactive data visualizations, and interface prototypes published seamlessly via GitHub Pages.

## Live Portal

Access the published central hub and research reports:
- **Central Knowledge Hub**: [https://jjjoelyoung.github.io/task-html/](https://jjjoelyoung.github.io/task-html/)

---

## Architecture & Directory Structure

This repository is designed with strict domain separation, allowing new artifacts to be added without breaking existing links or requiring any build step:

```text
task-html/
├── index.html                   # Central navigation portal & live searchable dashboard
├── reports/                     # In-depth research reports and strategic analyses
│   ├── equity/                  # Single-stock research (e.g., 2330-tsmc-20261109.html, 2501-cathay-real-estate.html, 8299-phison-20261109.html)
│   ├── industry/                # Thematic industry supply chain studies
│   └── macro/                   # Macroeconomic trends and liquidity tracking
├── scripts/                     # Data acquisition pipelines, generator scripts, and E2E test suites
│   └── equity/                  # Single-stock research pipelines (e.g., 2330-20261109/, 2501/, 8299-20261109/)
├── visualizers/                 # Interactive charts, backtests, and data tools
├── prototypes/                  # UI/UX mockups, design systems, and component drafts
├── docs/                        # Technical specifications, cheatsheets, and manuals
├── .gitignore                   # Standard ignore rules
└── README.md                    # Project documentation and publishing guide
```

---

## Published Deliverables

| Category | Deliverable | Live Link | Local Path |
| :--- | :--- | :--- | :--- |
| **Equity Research** | [2492 華新科 (Walsin Technology) 360度綜合深度投資分析報告](https://jjjoelyoung.github.io/task-html/reports/equity/2492-walsin-tech-20261110.html) | [View Online](https://jjjoelyoung.github.io/task-html/reports/equity/2492-walsin-tech-20261110.html) | [`reports/equity/2492-walsin-tech-20261110.html`](./reports/equity/2492-walsin-tech-20261110.html) |
| **Equity Research** | [2330 台積電 (TSMC) 360度綜合深度投資分析報告](https://jjjoelyoung.github.io/task-html/reports/equity/2330-tsmc-20261109.html) | [View Online](https://jjjoelyoung.github.io/task-html/reports/equity/2330-tsmc-20261109.html) | [`reports/equity/2330-tsmc-20261109.html`](./reports/equity/2330-tsmc-20261109.html) |
| **Equity Research** | 8299 Phison Electronics (群聯電子) 360° Comprehensive Analysis | [View Online](https://jjjoelyoung.github.io/task-html/reports/equity/8299-phison-20261109.html) | [`reports/equity/8299-phison-20261109.html`](./reports/equity/8299-phison-20261109.html) |
| **Equity Research** | 2501 Cathay Real Estate (國泰建設) 360° Comprehensive Analysis | [View Online](https://jjjoelyoung.github.io/task-html/reports/equity/2501-cathay-real-estate.html) | [`reports/equity/2501-cathay-real-estate.html`](./reports/equity/2501-cathay-real-estate.html) |

---

## Deployment via GitHub Pages

This project requires zero dependencies or build scripts (`node_modules`, Webpack, Vite, etc.). Every deliverable is an autonomous, standalone HTML artifact.

### How to Enable GitHub Pages
1. Navigate to the repository on GitHub: `https://github.com/JJJoelYoung/task-html`.
2. Go to **Settings** > **Pages** (under the "Code and automation" section).
3. Under **Build and deployment**:
   - **Source**: Select `Deploy from a branch`.
   - **Branch**: Select `master` (or `main`), and set directory to `/ (root)`.
   - Click **Save**.
4. The deployment will be live within 30 to 60 seconds at:  
   `https://jjjoelyoung.github.io/task-html/`

---

## Adding New Deliverables

To add a new HTML report or tool:
1. Place your self-contained `.html` file into the appropriate domain directory (e.g., `reports/equity/2330-tsmc.html`).
2. Add a new card entry in `index.html` within `<main class="artifacts-grid">` with its corresponding `data-category` and link.
3. Commit and push:
   ```bash
   git add .
   git commit -m "feat(equity): add 2330 tsmc research report"
   git push origin master
   ```
4. GitHub Pages will automatically serve the new page at:  
   `https://jjjoelyoung.github.io/task-html/reports/equity/2330-tsmc.html`

---

## License

This repository is maintained for research, analytical, and archival purposes.
