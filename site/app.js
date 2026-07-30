const translations = {
  zh: {
    pageTitle: "Leon Lai · AWS Solutions Architect 作品集",
    pageDescription: "從四個真實營運問題出發，介紹一套成本可控、可治理、可驗證的 AWS 遊戲數據平台。",
    skip: "跳到主要內容",
    navProblems: "營運問題",
    navArchitecture: "系統架構",
    navWorkflows: "四個工作流",
    navDemo: "Demo",
    navEvidence: "驗證證據",
    heroEyebrow: "LEON LAI · BUSINESS-FIRST AWS SA PORTFOLIO",
    heroTitle1: "一套治理模型，",
    heroTitle2: "支撐四種遊戲營運工作流。",
    heroLede: "將異常偵測、實驗運營、臨時分析與合作夥伴支援，建立在共用的資料定義、權限邊界與成本控制上。",
    seeArchitecture: "理解系統架構",
    seeDemo: "查看 Demo 路徑",
    heroScope: "Synthetic data · Verified PoC · 不宣稱 production workload 經驗",
    snapshot: "PROJECT SNAPSHOT",
    publicStatus: "Public · CI passing",
    statWorkflows: "operating workflows",
    statTests: "offline tests",
    statCost: "monthly gross model",
    statAlwaysOn: "always-on compute",
    snapshotFoot: "ap-northeast-1 · Serverless-first · Cost-bounded",
    problemsKicker: "THE OPERATING REALITY",
    problemsTitle: "先有營運問題，才有架構。",
    problemsIntro: "這些不是為了套 AWS 服務而整理出的抽象需求，而是會反覆消耗分析、營運、客服與工程資源的工作情境。",
    m1Short: "異常／套利",
    p1Title: "沒有主動監控，只能被動發現。",
    p1Body: "數據缺乏主動監控；一旦留存或營收下滑，通常要等到人為發現才會開始處理，存在時間落差，也讓團隊只能被動應對。另外，當詐欺玩家採用未曾遇過的套利手法時，也很難只靠既有規則識別。",
    corePriority: "CORE PRIORITY",
    m2Short: "實驗運營",
    p2Title: "並行實驗的狀態存在每個人的腦中。",
    p2Body: "不同遊戲的 A/B testing 同時進行時，沒有中央化方式查看並行實驗狀態，得一個一個問人，或等到站會才知道。",
    p2SecondaryIntro: "這個核心問題同時還伴隨兩個次要、但會持續增加營運成本的問題：",
    p2Secondary1: "SRM、guardrail 依賴人工抽查，異常實驗停止有延遲。",
    p2Secondary2: "相同 data feature 因為由不同組員負責而重複開發。",
    m3Short: "臨時分析",
    p3Title: "Dashboard 回答不了突然出現的「為什麼」。",
    p3Body: "Dashboard 可以回答固定問題，但當老闆、業務或客戶突然詢問「今天營收為什麼掉了？」時，現有 dashboard 往往無法直接回答。",
    p3Impact: "這類提問通常伴隨急迫性，又會在不可預期的時間出現，進一步加重分析人員的工作負擔；當客戶數量增加，問題頻率也會隨之上升。",
    m4Short: "合作夥伴支援",
    p4Title: "重複問題一路升級到工程師。",
    p4Body: "不同時區的合作夥伴經常反覆詢問類似的產品對接與整合問題：一方面客服需要重複回答；另一方面，若客服無法處理，問題就會升級到工程師層面，進一步增加開發負擔。",
    architectureKicker: "SYSTEM SHAPE & BOUNDARIES",
    architectureTitle: "三條工作流共用資料湖；第四條走獨立知識路徑。",
    architectureIntro: "這裡只呈現元件、資料流與邊界；為什麼暫時不用其他服務，留到 Decisions 再談。",
    dataLaneLabel: "M1 · M2 · M3 共用",
    sourceLabel: "INPUT",
    sourceTitle: "Game events",
    sourceBody: "Simulated · scripted scenarios",
    foundationLabel: "GOVERNED FOUNDATION",
    foundationTitle: "同一套資料定義與租戶邊界",
    metricDefinition: "KPI_DEFINITIONS.md · 共用指標邏輯",
    lakeIsolation: "Glue Catalog · Lake Formation row filters",
    architectureM1: "偵測",
    architectureM2: "實驗運營",
    architectureM3: "分析",
    supportLaneLabel: "M4 獨立語料",
    partnerDocsTitle: "Partner documents",
    partnerDocsBody: "Game provider · client operator",
    supportNodeTitle: "Partner support",
    supportNodeBody: "澄清 · 回答 · 升級",
    engineeringTitle: "客服／工程師",
    engineeringBody: "只有需要判斷時才介入",
    sharedRailTitle: "SHARED CONTROL PLANE",
    sharedIdentity: "身份決定可見範圍",
    sharedFacts: "Code 決定數字、路由與揭露",
    sharedCost: "預設部署受成本邊界約束",
    implementedLegend: "已實作整合",
    humanLegend: "人工決策／升級",
    architectureBoundary: "M4 不讀取 Gold tables；它與資料工作流共用控制原則，但不是同一條資料管線。",
    workflowsKicker: "SYSTEM OWNS REPETITION · PEOPLE OWN JUDGEMENT",
    workflowsTitle: "四個工作流，改變四種人的工作方式。",
    workflowsIntro: "每張卡只回答：原本怎麼做、系統接手什麼、人保留什麼決策，以及目前真正的實作邊界。",
    beforeLabel: "原本怎麼做",
    systemLabel: "系統接手",
    humanLabel: "人保留決策",
    boundaryLabel: "實作邊界",
    wf1Title: "異常與套利偵測",
    wf1Before: "依賴人主動查看報表，發現下滑後才開始追查；套利調查依賴既有經驗。",
    wf1System: "定期檢查 DAU、GGR、成熟 cohort 留存，並輸出 threshold、baseline 與風險證據。",
    wf1Human: "判斷根因、採取營運處置；套利結果只進入人工風險審查。",
    wf1Boundary: "套利目前是規則式，只識別已定義的雙訊號模式，不宣稱能抓未知手法。",
    wf3Title: "Analytics NL Assistant",
    wf3Before: "突發的 what／why 問題打斷分析師，還要重新查基線、遊戲別與共變動。",
    wf3System: "允許清單 SQL 回答 what；first-look 與 diagnose 組合證據回答 why；答不了就建 ticket。",
    wf3Human: "判讀營運脈絡、確認根因，並決定後續處置。",
    wf3Boundary: "只支援受治理的 KPI 與查詢模板；沒有 free-form text-to-SQL，也不支援未治理的 country／player 維度。",
    wf2Title: "實驗運營平台",
    wf2Before: "並行實驗狀態散落在人與站會中；SRM、guardrail 靠人工抽查，共用 feature 重複開發。",
    wf2System: "中央 registry、IAM-derived owner、SRM、guardrail、allocation kill switch 與共享 feature registry。",
    wf2Human: "決定假設、指標、是否採納結果，以及異常實驗後的產品處置。",
    wf2Boundary: "監控 cadence 最差為一小時；目前是本機簽名 console，尚未提供 hosted SSO team UI。",
    wf4Title: "合作夥伴支援 Chatbot",
    wf4Before: "客服重複回答整合問題；無法處理時再把缺乏脈絡的問題轉給工程師。",
    wf4System: "依身份選擇 provider／operator 語料，先澄清，再回答或建立可追蹤的 escalation。",
    wf4Human: "處理文件無法回答、需要產品判斷或真正涉及工程變更的案件。",
    wf4Boundary: "使用模擬 IAM 身份與小型語料；partner IdP、CRM delivery、時區 profile 尚未 production-ready。",
    demoKicker: "FOUR CHAPTERS · UNDER TWO MINUTES",
    demoTitle: "先理解工作流，再看它實際輸出什麼。",
    demoIntro: "這個互動導覽同時是最終兩分鐘影片的章節設計：每段只呈現痛點、執行結果、人的決策與邊界。",
    demoM1: "M1 · Detect",
    demoM1Time: "25 秒",
    demoM3: "M3 · Investigate",
    demoM3Time: "25 秒",
    demoM2: "M2 · Experiment Ops",
    demoM2Time: "35 秒 · core",
    demoM4: "M4 · Support",
    demoM4Time: "25 秒",
    demoPainLabel: "PAIN",
    demoResultLabel: "RESULT",
    demoHumanLabel: "HUMAN DECISION",
    demoBoundaryLabel: "BOUNDARY",
    loopDetect: "Detect",
    loopFirstLook: "First look",
    loopInvestigate: "Investigate",
    loopAct: "Act",
    loopValidate: "Validate",
    loopNote: "這條閉環只適用 KPI／留存異常。套利偵測走獨立的 flagged players → human review；M2 只在適合以受控實驗驗證時介入。",
    decisionsKicker: "NOT NOW — AND WHAT WOULD CHANGE THE DECISION",
    decisionsTitle: "不逐項背服務；只談三類判準。",
    decisionsIntro: "每一類 trade-off 都回答同一件事：現在為什麼不需要，以及什麼可量測條件會讓答案翻轉。",
    decision1Category: "WORKLOAD ECONOMICS",
    decision1Title: "目前的使用頻率，值得支付常駐成本嗎？",
    nowLabel: "NOW",
    flipLabel: "DECISION FLIPS WHEN",
    decision1Now: "資料量小、查詢間歇；預設採用 request-priced 或 scale-to-zero 元件，Kinesis 只做短生命週期示範。",
    decision1Flip: "出現持續查詢併發、穩定高流量，或 sub-minute SLA 成為正式需求。",
    decision2Category: "DATA ACCESS PATTERN",
    decision2Title: "真的需要線上低延遲 serving 或大規模 retrieval 嗎？",
    decision2Now: "Feature 用於 batch analysis；合作夥伴 corpus 小且可受控放入 context，現階段不需要新增 serving 與 retrieval 平面。",
    decision2Flip: "Feature 需要毫秒級線上查詢，或文件量超出 in-context 方法可治理的範圍。",
    decision3Category: "MANAGED WORKFLOW VS CONTROL",
    decision3Title: "應該購買完整工作流，還是保留較窄但可驗證的控制？",
    decision3Now: "PoC 使用窄範圍自訂流程，展示 SQL allowlist、數字所有權、tenant scope 與 disclosure control。",
    decision3Flip: "真實團隊需要完整 BI、自助報表、企業搜尋、內容維護與使用者管理，managed workflow 的組織價值開始更高。",
    learningsKicker: "THREE IMPLEMENTATION TRAPS",
    learningsTitle: "不是心得，而是測試後真的改了設計。",
    learningsIntro: "這些問題是在建置與驗證這個 PoC 時發現，不是宣稱來自 production incident。",
    learning1Title: "看得到 row filter，不代表租戶真的被隔離。",
    assumedLabel: "I ASSUMED",
    learning1Assumed: "建立 Lake Formation row-level filter 後，各 tenant 就只能看到自己的資料。",
    learning1Found: "Glue table 的向下相容 grant 仍可能把權限交回 IAM，讓 filter 看起來存在、實際卻是 no-op；直接 S3 GetObject 也是另一條繞過路徑。",
    changedLabel: "DESIGN CHANGED",
    learning1Changed: "撤銷該表的 compatibility grant、移除 analyst 的直接 S3 data access，再同時驗證 Athena 只看得到自己的 site，且 GetObject 必須被拒。",
    learning1Takeaway: "租戶隔離只有在繞過路徑也失敗時才是真的。",
    learning2Title: "同一場異常，第一天會響，第三天可能不再響。",
    learning2Assumed: "只要 DAU 持續低迷，EWMA detector 就會持續認為它異常。",
    learning2Day1: "約 3.9σ → ALERT",
    learning2Day3Strong: "2 個低迷日已進入 window",
    learning2Day3: "baseline 下移、標準差擴大 → NO ALERT",
    learning2Changed: "將目前 detector 明確定義為 onset detection：負責盡早觸發第一次調查，不假裝它同時管理持續事件狀態；production 若要持續告警，需另保留不會適應的 reference baseline。",
    learning2Takeaway: "偵測「事件開始」與追蹤「事件仍在發生」是兩個不同問題。",
    learning3Title: "Prompt 說不能洩漏，模型仍然洩漏了。",
    learning3Assumed: "明確要求模型不得顯示內部文件名稱與 ID，就足以保護對外回答。",
    learning3Leak: "“Document ID: [internal identifier]”",
    learning3Changed: "在送給合作夥伴前，由 deterministic validator 檢查並替換不安全輸出；完整證據只保留在內部 audit path。",
    learning3Takeaway: "Prompt 是要求；code validator 才是 enforcement boundary。",
    evidenceKicker: "CLAIMS NEED EVIDENCE",
    evidenceTitle: "最後只談可以回到程式、測試或 AWS 紀錄的主張。",
    evidenceIntro: "限制已放回各 workflow；這裡只留下能被驗證的證據。",
    evidenceTests: "offline tests passing",
    evidenceStacks: "default CDK stacks synthesize",
    evidenceAws: "baseline exercised against AWS",
    evidenceCost: "gross Cost Explorer usage snapshot",
    evidenceIsolation: "Athena scoped · direct S3 denied",
    evidenceRing: "scripted ring players flagged",
    evidenceAnswer: "assistant answer matched Athena",
    evidenceTeardown: "Kinesis teardown independently verified",
    architectureLink: "Architecture & trade-offs",
    costLink: "Cost evidence & scale model",
    isolationLink: "Tenant isolation proof",
    lessonsLink: "Designs changed by testing",
    scopeTitle: "Honest scope",
    scopeBody: "這是使用 synthetic data 的 verified PoC。最新版增量已通過本機與 CI 驗證，但沒有重新部署到付費 AWS 帳號，因此不宣稱目前 commit 是 production deployment。",
    closingKicker: "THE TAKEAWAY",
    closingTitle: "不是用了多少 AWS 服務，而是每個服務解決了什麼問題。",
    closingBody: "這個專案展示我如何把營運摩擦翻譯成可治理的系統、把人的判斷留在人手上，並在增加服務以前先說清楚成本、控制與採用門檻。",
    exploreRepo: "Explore the repository",
    backTop: "回到頂部",
    footerNote: "Synthetic data · Verified PoC · Public repository",
    languageChanged: "已切換為繁體中文",
  },
  en: {
    pageTitle: "Leon Lai · AWS Solutions Architect Portfolio",
    pageDescription: "A business-first walkthrough of a governed, cost-conscious and verifiable AWS game data platform.",
    skip: "Skip to main content",
    navProblems: "Problems",
    navArchitecture: "Architecture",
    navWorkflows: "Workflows",
    navDemo: "Demo",
    navEvidence: "Evidence",
    heroEyebrow: "LEON LAI · BUSINESS-FIRST AWS SA PORTFOLIO",
    heroTitle1: "One governance model.",
    heroTitle2: "Four game-operations workflows.",
    heroLede: "Anomaly detection, experiment operations, ad-hoc analytics and partner support share clear data definitions, access boundaries and cost controls.",
    seeArchitecture: "Understand the architecture",
    seeDemo: "Explore the demo path",
    heroScope: "Synthetic data · Verified PoC · No production-workload claim",
    snapshot: "PROJECT SNAPSHOT",
    publicStatus: "Public · CI passing",
    statWorkflows: "operating workflows",
    statTests: "offline tests",
    statCost: "monthly gross model",
    statAlwaysOn: "always-on compute",
    snapshotFoot: "ap-northeast-1 · Serverless-first · Cost-bounded",
    problemsKicker: "THE OPERATING REALITY",
    problemsTitle: "The operating problem comes before the architecture.",
    problemsIntro: "These are not abstract requirements reverse-engineered to fit AWS services. They are recurring situations that consume analyst, operations, support and engineering time.",
    m1Short: "Anomaly / arbitrage",
    p1Title: "Without active monitoring, discovery stays reactive.",
    p1Body: "Data was not actively monitored. When retention or revenue dropped, the team lost time waiting for someone to notice and could only respond after the fact. Previously unseen arbitrage techniques were also difficult to identify with existing rules.",
    corePriority: "CORE PRIORITY",
    m2Short: "Experiment operations",
    p2Title: "Parallel experiment status lived in people's heads.",
    p2Body: "When different games ran A/B tests at the same time, there was no central way to see their status. People had to ask each owner or wait for the stand-up.",
    p2SecondaryIntro: "That core problem came with two smaller issues that kept adding operating cost:",
    p2Secondary1: "SRM and guardrails were spot-checked manually, delaying abnormal experiment stops.",
    p2Secondary2: "Shared data features were rebuilt by different owners.",
    m3Short: "Ad-hoc analytics",
    p3Title: "Dashboards did not answer a sudden “why?”",
    p3Body: "Dashboards handled fixed questions, but they could not directly answer an executive, commercial lead or client asking, “Why did revenue drop today?”",
    p3Impact: "These questions were urgent and arrived at unpredictable times, increasing analyst workload. As the client base grew, so did their frequency.",
    m4Short: "Partner support",
    p4Title: "Repeated questions escalated all the way to engineering.",
    p4Body: "Partners across time zones repeatedly asked similar product-integration questions. Support had to answer the same issues, and anything it could not resolve escalated to engineers, adding development workload.",
    architectureKicker: "SYSTEM SHAPE & BOUNDARIES",
    architectureTitle: "Three workflows share the lake. The fourth follows a separate knowledge path.",
    architectureIntro: "This section shows components, data flow and boundaries only. Why other services are not used yet belongs in Decisions.",
    dataLaneLabel: "Shared by M1 · M2 · M3",
    sourceLabel: "INPUT",
    sourceTitle: "Game events",
    sourceBody: "Simulated · scripted scenarios",
    foundationLabel: "GOVERNED FOUNDATION",
    foundationTitle: "One data definition, one tenant boundary",
    metricDefinition: "KPI_DEFINITIONS.md · shared metric logic",
    lakeIsolation: "Glue Catalog · Lake Formation row filters",
    architectureM1: "Detect",
    architectureM2: "Experiment Ops",
    architectureM3: "Analytics",
    supportLaneLabel: "M4 isolated corpus",
    partnerDocsTitle: "Partner documents",
    partnerDocsBody: "Game provider · client operator",
    supportNodeTitle: "Partner support",
    supportNodeBody: "Clarify · answer · escalate",
    engineeringTitle: "Support / engineering",
    engineeringBody: "Only when judgement is required",
    sharedRailTitle: "SHARED CONTROL PLANE",
    sharedIdentity: "Identity determines scope",
    sharedFacts: "Code owns facts, routing and disclosure",
    sharedCost: "The default deployment is cost-bounded",
    implementedLegend: "Implemented integration",
    humanLegend: "Human decision / escalation",
    architectureBoundary: "M4 does not read Gold tables. It shares control principles with the data workflows, but it is not part of the same data pipeline.",
    workflowsKicker: "SYSTEM OWNS REPETITION · PEOPLE OWN JUDGEMENT",
    workflowsTitle: "Four workflows change how four groups of people work.",
    workflowsIntro: "Each card answers only four questions: what happened before, what the system takes over, what people still decide, and the real implementation boundary.",
    beforeLabel: "BEFORE",
    systemLabel: "SYSTEM TAKES OVER",
    humanLabel: "PEOPLE DECIDE",
    boundaryLabel: "IMPLEMENTATION BOUNDARY",
    wf1Title: "Anomaly & arbitrage detection",
    wf1Before: "People had to check reports and begin investigation after noticing a drop; arbitrage review depended on known experience.",
    wf1System: "Scheduled DAU, GGR and mature-cohort retention checks emit thresholds, baselines and explainable risk evidence.",
    wf1Human: "People identify root cause and choose the operational response; arbitrage results only enter human risk review.",
    wf1Boundary: "Arbitrage is currently rule-based. It detects a defined two-signal pattern and makes no unknown-technique claim.",
    wf3Title: "Analytics NL Assistant",
    wf3Before: "Sudden what/why questions interrupted analysts, who had to rebuild baseline, per-game and co-movement analysis.",
    wf3System: "Allow-listed SQL answers what; first-look and diagnose assemble evidence for why; unsupported work becomes a durable ticket.",
    wf3Human: "People interpret operating context, confirm root cause and choose what to do next.",
    wf3Boundary: "Only governed KPIs and query templates are supported. There is no free-form text-to-SQL or ungoverned country/player analysis.",
    wf2Title: "Experiment operations platform",
    wf2Before: "Parallel experiment status lived in people and stand-ups; SRM and guardrails were manual, and shared features were rebuilt.",
    wf2System: "A central registry, IAM-derived ownership, SRM, guardrails, an allocation kill switch and a shared feature registry.",
    wf2Human: "People choose hypotheses and metrics, decide whether to trust a result, and own the product response.",
    wf2Boundary: "Worst-case monitoring cadence is one hour. The signed console is local; there is no hosted SSO team UI yet.",
    wf4Title: "Partner support chatbot",
    wf4Before: "Support repeated integration answers and forwarded unresolved questions to engineers without enough context.",
    wf4System: "Identity selects the provider/operator corpus. The system clarifies first, then answers or creates a traceable escalation.",
    wf4Human: "People handle questions the documentation cannot answer, product judgement and real engineering changes.",
    wf4Boundary: "The PoC uses simulated IAM identities and a small corpus. Partner IdP, CRM delivery and time-zone profiles are not production-ready.",
    demoKicker: "FOUR CHAPTERS · UNDER TWO MINUTES",
    demoTitle: "Understand the workflow first; then inspect what it actually outputs.",
    demoIntro: "This interactive walkthrough is also the chapter plan for the final two-minute recording. Each chapter shows the pain, the run result, the human decision and the boundary.",
    demoM1: "M1 · Detect",
    demoM1Time: "25 sec",
    demoM3: "M3 · Investigate",
    demoM3Time: "25 sec",
    demoM2: "M2 · Experiment Ops",
    demoM2Time: "35 sec · core",
    demoM4: "M4 · Support",
    demoM4Time: "25 sec",
    demoPainLabel: "PAIN",
    demoResultLabel: "RESULT",
    demoHumanLabel: "HUMAN DECISION",
    demoBoundaryLabel: "BOUNDARY",
    loopDetect: "Detect",
    loopFirstLook: "First look",
    loopInvestigate: "Investigate",
    loopAct: "Act",
    loopValidate: "Validate",
    loopNote: "This loop covers KPI and retention anomalies only. Arbitrage follows a separate flagged players → human review path; M2 appears only when a controlled experiment is the right validation method.",
    decisionsKicker: "NOT NOW — AND WHAT WOULD CHANGE THE DECISION",
    decisionsTitle: "Three decision categories—not a service-by-service recital.",
    decisionsIntro: "Every trade-off answers the same question: why the service is unnecessary now, and what measurable condition would flip the decision.",
    decision1Category: "WORKLOAD ECONOMICS",
    decision1Title: "Does this usage pattern justify paying while idle?",
    nowLabel: "NOW",
    flipLabel: "DECISION FLIPS WHEN",
    decision1Now: "Data is small and queries are intermittent. Defaults are request-priced or scale-to-zero; Kinesis is an ephemeral demonstration only.",
    decision1Flip: "Sustained query concurrency, steady high throughput or a formal sub-minute SLA appears.",
    decision2Category: "DATA ACCESS PATTERN",
    decision2Title: "Is low-latency online serving or large-scale retrieval actually required?",
    decision2Now: "Features serve batch analysis. The partner corpus is small enough for controlled in-context use, so another serving or retrieval plane adds no value yet.",
    decision2Flip: "Features need millisecond online lookups or the corpus outgrows a governable in-context approach.",
    decision3Category: "MANAGED WORKFLOW VS CONTROL",
    decision3Title: "Buy a complete workflow, or keep a narrow but verifiable control surface?",
    decision3Now: "The PoC uses a narrow custom path to demonstrate SQL allowlists, numeric ownership, tenant scope and disclosure control.",
    decision3Flip: "A real team needs full BI, self-service reporting, enterprise search, content operations and user management—making the managed workflow more valuable.",
    learningsKicker: "THREE IMPLEMENTATION TRAPS",
    learningsTitle: "Not reflections—tests that actually changed the design.",
    learningsIntro: "These were discovered while building and validating this PoC. They are not presented as production incidents.",
    learning1Title: "A visible row filter did not prove tenant isolation.",
    assumedLabel: "I ASSUMED",
    learning1Assumed: "Once a Lake Formation row-level filter existed, every tenant could only see its own rows.",
    learning1Found: "A Glue table's backward-compatibility grant could defer access back to IAM, leaving a visible filter as a no-op. Direct S3 GetObject was a second bypass path.",
    changedLabel: "DESIGN CHANGED",
    learning1Changed: "Revoke that table's compatibility grant, remove direct analyst access to the data, then verify both outcomes: Athena sees one site and GetObject is denied.",
    learning1Takeaway: "Tenant isolation is real only when the bypass path fails too.",
    learning2Title: "The same incident alerted on day one—but not on day three.",
    learning2Assumed: "If DAU stayed depressed, the EWMA detector would keep treating it as abnormal.",
    learning2Day1: "about 3.9σ → ALERT",
    learning2Day3Strong: "2 depressed days entered the window",
    learning2Day3: "baseline fell, deviation widened → NO ALERT",
    learning2Changed: "Define this detector as onset detection: it starts the first investigation but does not pretend to manage persistent incident state. Production persistence would require a separate non-adapting reference baseline.",
    learning2Takeaway: "Detecting an incident's onset and tracking that it remains active are different problems.",
    learning3Title: "The prompt prohibited a leak. The model leaked anyway.",
    learning3Assumed: "Explicitly telling the model not to show internal document names or IDs was enough to protect an external answer.",
    learning3Leak: "“Document ID: [internal identifier]”",
    learning3Changed: "A deterministic validator now checks and replaces unsafe output before delivery; full evidence remains only on the internal audit path.",
    learning3Takeaway: "A prompt is a request. Code validation is the enforcement boundary.",
    evidenceKicker: "CLAIMS NEED EVIDENCE",
    evidenceTitle: "Only claims that trace back to code, tests or AWS evidence remain.",
    evidenceIntro: "Limits sit with each workflow. This final section contains verification only.",
    evidenceTests: "offline tests passing",
    evidenceStacks: "default CDK stacks synthesize",
    evidenceAws: "baseline exercised against AWS",
    evidenceCost: "gross Cost Explorer usage snapshot",
    evidenceIsolation: "Athena scoped · direct S3 denied",
    evidenceRing: "scripted ring players flagged",
    evidenceAnswer: "assistant answer matched Athena",
    evidenceTeardown: "Kinesis teardown independently verified",
    architectureLink: "Architecture & trade-offs",
    costLink: "Cost evidence & scale model",
    isolationLink: "Tenant isolation proof",
    lessonsLink: "Designs changed by testing",
    scopeTitle: "Honest scope",
    scopeBody: "This is a verified PoC using synthetic data. The latest increment passed local and CI validation but was not redeployed to the paid AWS account, so the current commit is not presented as a production deployment.",
    closingKicker: "THE TAKEAWAY",
    closingTitle: "The point is not how many AWS services I used, but what each one solves.",
    closingBody: "This project shows how I translate operating friction into a governed system, keep human judgement with people, and state cost, control and adoption thresholds before adding services.",
    exploreRepo: "Explore the repository",
    backTop: "Back to top",
    footerNote: "Synthetic data · Verified PoC · Public repository",
    languageChanged: "Language changed to English",
  },
};

const demoChapters = {
  zh: {
    m1: {
      title: "M1 / VERIFIED DEMO OUTPUT",
      pain: "留存／營收下滑需要等人發現；規則式套利需要可解釋證據。",
      result: "首日 KPI 下滑被標示；6 個 scripted ring players 全數進入 REVIEW_REQUIRED。",
      terminal: [
        "$ run module1 demo --as-of 2026-06-10",
        "site_b / dau",
        "actual=91 · EWMA baseline=204 · deviation≈3.9σ",
        "status=ALERT · evidence_window=preserved",
        "",
        "arbitrage review",
        "flagged=6/6 · decision=REVIEW_REQUIRED",
      ].join("\n"),
      human: "確認根因、選擇營運處置，並審查被標示玩家。",
      boundary: "未知套利手法沒有 reviewed labels，因此不宣稱偵測能力。",
    },
    m3: {
      title: "M3 / GOVERNED ANALYTICS OUTPUT",
      pain: "急迫的 what／why 問題會打斷分析師，dashboard 無法直接回答。",
      result: "Allow-listed SQL 回答數字；first-look 在 alert 後自動整理基線與共變動。",
      terminal: [
        '$ ask "What was GGR for site_a in the last week?"',
        "category=answerable",
        "answer=891.83 USD",
        "direct Athena cross-check=891.83 USD · MATCH",
        "",
        "site_b first-look",
        "DAU 91 vs 7d avg 205.5714 (-55.73%)",
        "DAU and GGR moved in the same direction",
      ].join("\n"),
      human: "結合營運脈絡判斷根因，再決定行動。",
      boundary: "只支援受治理 KPI 與模板；答不了就建立 ticket，不生成任意 SQL。",
    },
    m2: {
      title: "M2 / THREE CONCURRENT EXPERIMENTS",
      pain: "並行實驗狀態分散，SRM 與 guardrail 依賴人工抽查。",
      result: "三種生命週期同時可見：正常分析、guardrail 自動停止、SRM hard fail。",
      terminal: [
        "$ run 3 concurrent experiments",
        "clean_winner    state=analyzed · lift=564.1%",
        "                 caveats=SMALL_SAMPLE,LARGE_EFFECT",
        "guardrail_stop  state=stopped_early",
        "                 ggr_usd_7d=-98.2912 < 0",
        "srm_violation   state=stopped_early",
        "                 p=0.000415 · analysis skipped",
        "grounding_check_passed=true",
      ].join("\n"),
      human: "判斷結果是否可信、要不要重跑，以及產品是否採納。",
      boundary: "這是刻意注入的 deterministic scenario；監控 cadence 最差為一小時。",
    },
    m4: {
      title: "M4 / SUPPORT & LEAKAGE CONTROL",
      pain: "重複整合問題消耗客服；處理不了的問題缺乏結構就轉給工程師。",
      result: "系統先澄清、再回答或建立 ticket；模型洩漏被 code validator 擋下。",
      terminal: [
        "$ run partner-support demo",
        "ambiguous question → NEEDS_CLARIFICATION",
        "engineering case   → ESCALATION · ticket=created",
        "out-of-scope       → deterministic refusal",
        "",
        "model output       → internal identifier detected",
        "validation         → FAILED_SAFE",
        "identifier reaching partner → NONE",
      ].join("\n"),
      human: "處理真正需要產品判斷或工程變更的 ticket。",
      boundary: "使用模擬身份與小型 corpus；沒有 production partner federation。",
    },
  },
  en: {
    m1: {
      title: "M1 / VERIFIED DEMO OUTPUT",
      pain: "Retention and revenue drops waited for human discovery; rule-based arbitrage needed explainable evidence.",
      result: "The first-day KPI drop was flagged; all six scripted ring players entered REVIEW_REQUIRED.",
      terminal: [
        "$ run module1 demo --as-of 2026-06-10",
        "site_b / dau",
        "actual=91 · EWMA baseline=204 · deviation≈3.9σ",
        "status=ALERT · evidence_window=preserved",
        "",
        "arbitrage review",
        "flagged=6/6 · decision=REVIEW_REQUIRED",
      ].join("\n"),
      human: "Confirm root cause, choose an operating response and review flagged players.",
      boundary: "There are no reviewed labels for unknown techniques, so no such coverage is claimed.",
    },
    m3: {
      title: "M3 / GOVERNED ANALYTICS OUTPUT",
      pain: "Urgent what/why questions interrupted analysts and did not fit dashboards.",
      result: "Allow-listed SQL owns the number; first-look assembles baseline and co-movement evidence after an alert.",
      terminal: [
        '$ ask "What was GGR for site_a in the last week?"',
        "category=answerable",
        "answer=891.83 USD",
        "direct Athena cross-check=891.83 USD · MATCH",
        "",
        "site_b first-look",
        "DAU 91 vs 7d avg 205.5714 (-55.73%)",
        "DAU and GGR moved in the same direction",
      ].join("\n"),
      human: "Combine operating context with evidence, identify root cause and decide what to do.",
      boundary: "Only governed KPI templates are supported. Unsupported work creates a ticket instead of arbitrary SQL.",
    },
    m2: {
      title: "M2 / THREE CONCURRENT EXPERIMENTS",
      pain: "Parallel status was scattered; SRM and guardrails depended on manual checks.",
      result: "Three lifecycles stay visible together: normal analysis, guardrail stop and SRM hard fail.",
      terminal: [
        "$ run 3 concurrent experiments",
        "clean_winner    state=analyzed · lift=564.1%",
        "                 caveats=SMALL_SAMPLE,LARGE_EFFECT",
        "guardrail_stop  state=stopped_early",
        "                 ggr_usd_7d=-98.2912 < 0",
        "srm_violation   state=stopped_early",
        "                 p=0.000415 · analysis skipped",
        "grounding_check_passed=true",
      ].join("\n"),
      human: "Decide whether the result is trustworthy, whether to rerun and whether the product should adopt it.",
      boundary: "These are deliberately injected deterministic scenarios; worst-case monitoring cadence is one hour.",
    },
    m4: {
      title: "M4 / SUPPORT & LEAKAGE CONTROL",
      pain: "Repeated integration questions consumed support; unresolved cases reached engineers without structure.",
      result: "The system clarifies, answers or creates a ticket; code blocks a model-authored internal identifier.",
      terminal: [
        "$ run partner-support demo",
        "ambiguous question → NEEDS_CLARIFICATION",
        "engineering case   → ESCALATION · ticket=created",
        "out-of-scope       → deterministic refusal",
        "",
        "model output       → internal identifier detected",
        "validation         → FAILED_SAFE",
        "identifier reaching partner → NONE",
      ].join("\n"),
      human: "Handle tickets that genuinely require product judgement or an engineering change.",
      boundary: "The PoC uses simulated identity and a small corpus; there is no production partner federation.",
    },
  },
};

let activeLanguage = "zh";
let activeDemo = "m1";

const languageButtons = [...document.querySelectorAll("[data-lang]")];
const demoButtons = [...document.querySelectorAll("[data-demo]")];
const announcer = document.querySelector(".language-announcer");
const metaDescription = document.querySelector('meta[name="description"]');

function renderDemo() {
  const chapter = demoChapters[activeLanguage][activeDemo];
  document.querySelector("#demo-window-title").textContent = chapter.title;
  document.querySelector("#demo-pain").textContent = chapter.pain;
  document.querySelector("#demo-result").textContent = chapter.result;
  document.querySelector("#demo-terminal").textContent = chapter.terminal;
  document.querySelector("#demo-human").textContent = chapter.human;
  document.querySelector("#demo-boundary").textContent = chapter.boundary;

  demoButtons.forEach((button) => {
    const selected = button.dataset.demo === activeDemo;
    button.setAttribute("aria-selected", String(selected));
    button.tabIndex = selected ? 0 : -1;
  });
}

function applyLanguage(language, announce = true) {
  activeLanguage = language;
  const copy = translations[language];
  document.documentElement.lang = language === "zh" ? "zh-Hant" : "en";
  document.title = copy.pageTitle;
  metaDescription.setAttribute("content", copy.pageDescription);

  document.querySelectorAll("[data-i18n]").forEach((element) => {
    const key = element.dataset.i18n;
    if (Object.hasOwn(copy, key)) {
      element.textContent = copy[key];
    }
  });

  languageButtons.forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.lang === language));
  });

  localStorage.setItem("leon-portfolio-language", language);
  renderDemo();

  if (announce) {
    announcer.textContent = copy.languageChanged;
  }
}

languageButtons.forEach((button) => {
  button.addEventListener("click", () => applyLanguage(button.dataset.lang));
});

demoButtons.forEach((button, index) => {
  button.addEventListener("click", () => {
    activeDemo = button.dataset.demo;
    renderDemo();
  });
  button.addEventListener("keydown", (event) => {
    if (!["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
      return;
    }
    event.preventDefault();
    let nextIndex = index;
    if (["ArrowDown", "ArrowRight"].includes(event.key)) {
      nextIndex = (index + 1) % demoButtons.length;
    } else if (["ArrowUp", "ArrowLeft"].includes(event.key)) {
      nextIndex = (index - 1 + demoButtons.length) % demoButtons.length;
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = demoButtons.length - 1;
    }
    demoButtons[nextIndex].focus();
    demoButtons[nextIndex].click();
  });
});

document.addEventListener("keydown", (event) => {
  const tag = document.activeElement?.tagName;
  if (event.key.toLowerCase() === "l" && !["INPUT", "TEXTAREA", "SELECT"].includes(tag)) {
    applyLanguage(activeLanguage === "zh" ? "en" : "zh");
  }
});

const storedLanguage = localStorage.getItem("leon-portfolio-language");
applyLanguage(storedLanguage === "en" ? "en" : "zh", false);

const progress = document.querySelector(".scroll-progress span");
const navigationLinks = [...document.querySelectorAll("nav a")];
const sections = [...document.querySelectorAll("[data-section]")];

function updateScrollState() {
  const scrollable = document.documentElement.scrollHeight - window.innerHeight;
  const ratio = scrollable > 0 ? window.scrollY / scrollable : 0;
  progress.style.transform = `scaleX(${Math.min(Math.max(ratio, 0), 1)})`;

  const marker = window.scrollY + window.innerHeight * 0.35;
  let current = "overview";
  sections.forEach((section) => {
    if (section.offsetTop <= marker) {
      current = section.id;
    }
  });
  navigationLinks.forEach((link) => {
    link.classList.toggle("active", link.getAttribute("href") === `#${current}`);
  });
}

window.addEventListener("scroll", updateScrollState, { passive: true });
window.addEventListener("resize", updateScrollState);
updateScrollState();

const revealElements = [...document.querySelectorAll(".reveal")];
if ("IntersectionObserver" in window && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.08, rootMargin: "0px 0px -36px" },
  );
  revealElements.forEach((element) => observer.observe(element));
} else {
  revealElements.forEach((element) => element.classList.add("is-visible"));
}
