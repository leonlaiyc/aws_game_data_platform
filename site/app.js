const translations = {
  zh: {
    pageTitle: "Aurora Games · AWS SA 作品集",
    pageDescription: "以四個營運痛點為起點，介紹一套成本優先、可治理、可驗證的 AWS 遊戲數據平台。",
    skip: "跳到主要內容",
    navStory: "系統故事",
    navModules: "四個模組",
    navDecisions: "成本取捨",
    navProof: "驗證證據",
    heroEyebrow: "BUSINESS-FIRST · COST-CONSCIOUS · VERIFIED PoC",
    heroTitle1: "從四個營運痛點，",
    heroTitle2: "到一個可驗證的 AWS 平台。",
    heroLede:
      "我沒有從服務清單開始，而是從「異常太晚發現、實驗狀態看不到、臨時分析打斷人、整合問題重複回答」開始。這個專案展示我如何把舊工作的營運問題，轉成一套有治理、有成本邊界、能被測試的雲端架構。",
    startTour: "開始 5 分鐘導覽",
    viewRepo: "查看 GitHub",
    keyboardHint: "快速切換語言",
    snapshot: "PROJECT SNAPSHOT",
    publicStatus: "Public · CI passing",
    statPains: "真實營運痛點",
    statTests: "離線測試",
    statIdle: "月固定成本模型",
    statAlwaysOn: "常駐運算服務",
    snapshotFoot: "ap-northeast-1 · Serverless-first · Synthetic data only",
    storyKicker: "ONE SYSTEM, NOT FOUR DEMOS",
    storyTitle: "一個異常，如何走完整個決策閉環",
    storyIntro: "自動化應該接手重複、容易漏掉的工作；假設形成與產品決策仍由人負責。這條界線在程式與架構圖裡都被明確標示。",
    manifesto: "只有偵測、沒有調查，只是在製造噪音；只有調查、沒有驗證，只是一個意見。",
    auto: "自動",
    human: "人工",
    flowDetect: "偵測下滑",
    flowDetectBody: "每日 DAU/GGR 與週級成熟 cohort 留存檢查。",
    flowDiagnose: "先做初步診斷",
    flowDiagnoseBody: "同一個警報自動拆解基線、遊戲別 GGR 與共變動。",
    flowHypothesis: "形成假設",
    flowHypothesisBody: "分析師閱讀證據，決定要驗證的產品假設。",
    humanJudgement: "Human judgement",
    flowExperiment: "安全跑實驗",
    flowExperimentBody: "中央 registry、SRM、guardrail 與 kill switch。",
    sidecarTitle: "合作夥伴支援在閉環之外，替團隊擋下重複問題。",
    sidecarBody: "真正需要工程師的問題才升級；其他問題由受眾隔離、可控成本的支援入口處理。",
    modulesKicker: "FOUR PAINS → FOUR RESPONSES",
    modulesTitle: "每個服務選擇，都要能回到一個營運問題",
    modulesIntro: "面試時我會先講「誰被什麼問題卡住」，再展示自動化、治理與證據；不是先背 AWS 服務名稱。",
    m1Domain: "DETECTION",
    m1Title: "異常與套利偵測",
    painLabel: "痛點",
    m1Pain: "留存／營收下滑太晚才被人工發現；新型套利手法難以辨識。",
    responseLabel: "架構回應",
    m1Response: "每日 DAU/GGR、週級成熟 cohort 留存，共用 SNS → 診斷路徑；已知規則只標示 REVIEW_REQUIRED。",
    m1Evidence1: "警報保留 actual、baseline、threshold 與 evidence window",
    m1Evidence2: "未知套利模型因缺少審核 labels 而明確不宣稱",
    coreModule: "核心模組",
    m2Domain: "EXPERIMENT OPS",
    m2Title: "實驗運營平台",
    m2Pain: "多款遊戲同時做 A/B testing，必須等站會或逐一問人才知道狀態。",
    m2Response: "中央 registry 顯示 owner、生命週期、SRM、guardrail 與 allocation；IAM 身分產生 provenance。",
    m2Evidence1: "關閉 allocation 與 exposure 寫入使用同一筆 transaction",
    m2Evidence2: "共享 feature registry 降低不同實驗重算相同特徵",
    m3Domain: "NL ANALYTICS",
    m3Title: "Analytics NL Assistant",
    m3Pain: "老闆、業務與客戶的突發問題不好用 dashboard 回答，持續打斷分析師。",
    m3Response: "允許清單 SQL 回答 what；diagnose 重用 first-look 回答 why；答不了就建立 durable ticket。",
    m3Evidence1: "沒有 free-form text-to-SQL，tenant scope 只來自身份",
    m3Evidence2: "所有數字由 code render，模型只寫質性文字",
    m4Domain: "PARTNER SUPPORT",
    m4Title: "合作夥伴支援 Chatbot",
    m4Pain: "不同時區、不同整合方向的夥伴反覆詢問相似問題，客服答不了又轉給工程師。",
    m4Response: "IAM 身分選擇 provider/operator 隔離語料；clarification、escalation、leakage guard 都由 code 決定。",
    m4Evidence1: "每個受眾每日最多 50 個有效 paid-path 請求",
    m4Evidence2: "API 全域 0.1 req/s、burst 2，未知身份 fail closed",
    decisionsKicker: "THE HARDEST REQUIREMENT",
    decisionsTitle: "不要讓作品集變成一張失控的帳單",
    decisionsIntro: "架構不是服務越多越好。每個預設資源都必須回答：閒置會不會收費？什麼指標才值得升級？",
    grossModel: "STEADY-STATE GROSS MODEL",
    perMonth: " / 月",
    costHeroBody: "固定成本主要來自 13 個 CloudWatch alarms；不是 compute。",
    modelMarker: "模型值 <$2",
    budgetMarker: "$5 預算警報",
    defaultTitle: "預設部署",
    defaultBody: "Lambda、Athena、DynamoDB on-demand、Step Functions、EventBridge、SNS/SQS。沒有流量就近乎不產生 data-plane 成本。",
    excludedTitle: "刻意排除",
    excludedBody: "NAT Gateway、RDS、OpenSearch、Redshift、EMR、常駐 Kinesis 與向量資料庫；目前規模沒有合理化其固定成本。",
    ephemeralTitle: "短生命週期例外",
    ephemeralBody: "Kinesis 只可用明確 flag 執行 deploy → demo → destroy → verify，不可能被預設 deploy --all 意外建立。",
    tradeoffPrompt: "面試追問：為什麼沒有 Redshift、Spark 或向量資料庫？",
    tradeoffAnswer: "因為我能說出採用門檻，而不是為了履歷放進一個還不需要的服務。",
    proofKicker: "CLAIMS NEED EVIDENCE",
    proofTitle: "不是架構圖說了算，是負向測試與失敗路徑說了算",
    proofIntro: "PoC 不等於 production 經驗；但每個作品集主張都應該有程式、測試、成本或誠實邊界可以追。",
    metricTests: "離線測試通過",
    metricStacks: "預設 CDK stacks 可 synth",
    metricAlerts: "公開安全 alerts",
    metricIsolation: "租戶隔離負向驗證",
    linkArchitecture: "架構與服務取捨",
    linkCost: "成本模型與 100× 推估",
    linkThreat: "威脅模型與剩餘風險",
    linkLessons: "五個實測後修正的設計",
    boundariesKicker: "HONEST BOUNDARIES",
    boundariesTitle: "我不會把還沒做到的事藏起來。",
    boundary1: "沒有真實產品 ingestion，因此不宣稱端到端 freshness SLA。",
    boundary2: "沒有 reviewed labels，因此不宣稱能抓未知套利手法。",
    boundary3: "沒有 partner IdP contract，因此 M3/M4 外部 federation 尚未 production-ready。",
    closingKicker: "THE INTERVIEW TAKEAWAY",
    closingTitle: "我想展示的不是「我用了多少 AWS 服務」。",
    closingBody: "而是我如何把營運摩擦翻譯成可治理的系統、如何讓 LLM 留在可控邊界內，以及如何在每個架構決策前先算成本與風險。",
    exploreCode: "探索完整程式碼",
    readBoundaries: "閱讀專案邊界",
    footerNote: "Fictional company · Synthetic data · Built for responsible discussion",
    backTop: "回到頂部 ↑",
    languageChanged: "已切換為繁體中文",
  },
  en: {
    pageTitle: "Aurora Games · AWS SA Portfolio",
    pageDescription: "A cost-conscious, governed and verifiable AWS game data platform, presented through four operating pains.",
    skip: "Skip to main content",
    navStory: "System story",
    navModules: "Four modules",
    navDecisions: "Cost choices",
    navProof: "Evidence",
    heroEyebrow: "BUSINESS-FIRST · COST-CONSCIOUS · VERIFIED PoC",
    heroTitle1: "Four operating pains.",
    heroTitle2: "One verifiable AWS platform.",
    heroLede:
      "I did not begin with a service catalogue. I began with late anomaly discovery, invisible experiment status, ad-hoc questions interrupting analysts, and repeated integration support. This project shows how I translated operating friction from my previous work into a governed, cost-bounded and testable cloud architecture.",
    startTour: "Start the 5-minute tour",
    viewRepo: "View GitHub",
    keyboardHint: "Quick language switch",
    snapshot: "PROJECT SNAPSHOT",
    publicStatus: "Public · CI passing",
    statPains: "operating pains",
    statTests: "offline tests",
    statIdle: "monthly idle model",
    statAlwaysOn: "always-on compute",
    snapshotFoot: "ap-northeast-1 · Serverless-first · Synthetic data only",
    storyKicker: "ONE SYSTEM, NOT FOUR DEMOS",
    storyTitle: "How one anomaly moves through a decision loop",
    storyIntro: "Automation owns the repetitive work that is easy to miss. Hypothesis formation and product decisions remain human. That boundary is explicit in both code and architecture.",
    manifesto: "Detection without investigation is noise. Investigation without validation is opinion.",
    auto: "AUTO",
    human: "HUMAN",
    flowDetect: "Detect the drop",
    flowDetectBody: "Daily DAU/GGR and weekly mature-cohort retention checks.",
    flowDiagnose: "Run a first look",
    flowDiagnoseBody: "The same alert triggers baseline, per-game GGR and co-movement evidence.",
    flowHypothesis: "Form a hypothesis",
    flowHypothesisBody: "An analyst reads the evidence and chooses what product idea to test.",
    humanJudgement: "Human judgement",
    flowExperiment: "Experiment safely",
    flowExperimentBody: "Central registry, SRM, guardrails and an allocation kill switch.",
    sidecarTitle: "Partner support sits beside the loop and absorbs repeated questions.",
    sidecarBody: "Only questions that genuinely need engineering are escalated; the rest go through an audience-isolated, cost-bounded support path.",
    modulesKicker: "FOUR PAINS → FOUR RESPONSES",
    modulesTitle: "Every service choice must trace back to an operating problem",
    modulesIntro: "In an interview, I start with who is blocked and why. Then I show the automation, governance and evidence—not a memorized list of AWS services.",
    m1Domain: "DETECTION",
    m1Title: "Anomaly & arbitrage detection",
    painLabel: "PAIN",
    m1Pain: "Retention and revenue drops are noticed too late; previously unseen arbitrage techniques are difficult to catch.",
    responseLabel: "RESPONSE",
    m1Response: "Daily DAU/GGR and weekly mature-cohort retention share an SNS → diagnosis path; known rules only emit REVIEW_REQUIRED.",
    m1Evidence1: "Alerts preserve actual, baseline, threshold and evidence window",
    m1Evidence2: "No unknown-technique claim without reviewed labels",
    coreModule: "CORE MODULE",
    m2Domain: "EXPERIMENT OPS",
    m2Title: "Experiment operations platform",
    m2Pain: "When many games run A/B tests in parallel, status only becomes visible in stand-ups or by asking people one by one.",
    m2Response: "A central registry shows owner, lifecycle, SRM, guardrails and allocation; IAM identity supplies provenance.",
    m2Evidence1: "Allocation closure and exposure writes share one transaction",
    m2Evidence2: "A shared feature registry reduces repeated feature computation",
    m3Domain: "NL ANALYTICS",
    m3Title: "Analytics NL Assistant",
    m3Pain: "Sudden executive, commercial and partner questions do not fit dashboards and repeatedly interrupt analysts.",
    m3Response: "Allow-listed SQL answers what; diagnose reuses first-look evidence for why; unsupported work becomes a durable ticket.",
    m3Evidence1: "No free-form text-to-SQL; tenant scope only comes from identity",
    m3Evidence2: "Code renders every number; the model only writes qualitative text",
    m4Domain: "PARTNER SUPPORT",
    m4Title: "Partner support chatbot",
    m4Pain: "Partners across time zones and integration directions repeat similar questions; unresolved cases consume engineering time.",
    m4Response: "IAM identity selects isolated provider/operator corpora; clarification, escalation and leakage controls are code-owned.",
    m4Evidence1: "At most 50 valid paid-path requests per audience per day",
    m4Evidence2: "Global API throttle of 0.1 req/s, burst 2; unknown identities fail closed",
    decisionsKicker: "THE HARDEST REQUIREMENT",
    decisionsTitle: "Do not let a portfolio become an uncontrolled bill",
    decisionsIntro: "Architecture is not a service-count contest. Every default resource must answer two questions: does it charge while idle, and what measurable trigger justifies it?",
    grossModel: "STEADY-STATE GROSS MODEL",
    perMonth: " / month",
    costHeroBody: "Most fixed cost comes from 13 CloudWatch alarms—not compute.",
    modelMarker: "Model <$2",
    budgetMarker: "$5 budget alarm",
    defaultTitle: "Default deployment",
    defaultBody: "Lambda, Athena, DynamoDB on-demand, Step Functions, EventBridge and SNS/SQS. With no traffic, data-plane cost approaches zero.",
    excludedTitle: "Deliberately excluded",
    excludedBody: "NAT Gateway, RDS, OpenSearch, Redshift, EMR, persistent Kinesis and a vector database. Current scale does not justify their fixed cost.",
    ephemeralTitle: "Ephemeral exception",
    ephemeralBody: "Kinesis only runs behind an explicit deploy → demo → destroy → verify flag and cannot be created by the default deploy --all path.",
    tradeoffPrompt: "Interview follow-up: why no Redshift, Spark or vector database?",
    tradeoffAnswer: "Because I can state the adoption trigger instead of adding a service the workload does not need.",
    proofKicker: "CLAIMS NEED EVIDENCE",
    proofTitle: "Architecture diagrams do not decide what is true—negative tests and failure paths do",
    proofIntro: "A PoC is not production experience. But every portfolio claim should trace to code, a test, a cost model or an honest boundary.",
    metricTests: "offline tests passing",
    metricStacks: "default CDK stacks synthesize",
    metricAlerts: "open public security alerts",
    metricIsolation: "tenant isolation verified both ways",
    linkArchitecture: "Architecture & service trade-offs",
    linkCost: "Cost model & 100× projection",
    linkThreat: "Threat model & residual risk",
    linkLessons: "Five designs changed by testing",
    boundariesKicker: "HONEST BOUNDARIES",
    boundariesTitle: "I do not hide what is not implemented.",
    boundary1: "No real product ingestion, so there is no end-to-end freshness SLA claim.",
    boundary2: "No reviewed labels, so there is no unknown-arbitrage coverage claim.",
    boundary3: "No partner IdP contract, so external M3/M4 federation is not production-ready.",
    closingKicker: "THE INTERVIEW TAKEAWAY",
    closingTitle: "The point is not how many AWS services I used.",
    closingBody: "It is how I translate operating friction into a governed system, keep LLMs inside enforceable boundaries, and price risk and cost before choosing architecture.",
    exploreCode: "Explore the full repository",
    readBoundaries: "Read the project boundaries",
    footerNote: "Fictional company · Synthetic data · Built for responsible discussion",
    backTop: "Back to top ↑",
    languageChanged: "Language changed to English",
  },
};

const languageButtons = [...document.querySelectorAll("[data-lang]")];
const translatable = [...document.querySelectorAll("[data-i18n]")];
const statusRegion = document.querySelector("#language-status");
const descriptionMeta = document.querySelector('meta[name="description"]');

function chooseInitialLanguage() {
  const urlLanguage = new URLSearchParams(window.location.search).get("lang");
  if (urlLanguage === "en" || urlLanguage === "zh") return urlLanguage;

  const stored = localStorage.getItem("aurora-demo-language");
  if (stored === "en" || stored === "zh") return stored;

  return navigator.language.toLowerCase().startsWith("zh") ? "zh" : "en";
}

function applyLanguage(language, announce = false) {
  const dictionary = translations[language];
  document.documentElement.lang = language === "zh" ? "zh-Hant" : "en";
  document.title = dictionary.pageTitle;
  descriptionMeta.setAttribute("content", dictionary.pageDescription);

  translatable.forEach((element) => {
    const key = element.dataset.i18n;
    if (dictionary[key] !== undefined) {
      element.textContent = dictionary[key];
    }
  });

  languageButtons.forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.lang === language));
  });

  localStorage.setItem("aurora-demo-language", language);
  const url = new URL(window.location.href);
  url.searchParams.set("lang", language);
  history.replaceState({}, "", url);

  if (announce) {
    statusRegion.textContent = dictionary.languageChanged;
  }
}

let currentLanguage = chooseInitialLanguage();
applyLanguage(currentLanguage);

languageButtons.forEach((button) => {
  button.addEventListener("click", () => {
    currentLanguage = button.dataset.lang;
    applyLanguage(currentLanguage, true);
  });
});

document.addEventListener("keydown", (event) => {
  const target = event.target;
  const isTyping =
    target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    target instanceof HTMLSelectElement ||
    target?.isContentEditable;

  if (!isTyping && event.key.toLowerCase() === "l" && !event.metaKey && !event.ctrlKey && !event.altKey) {
    currentLanguage = currentLanguage === "zh" ? "en" : "zh";
    applyLanguage(currentLanguage, true);
  }
});

const revealObserver = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("is-visible");
        revealObserver.unobserve(entry.target);
      }
    });
  },
  { threshold: 0.1 },
);

document.querySelectorAll(".reveal").forEach((element) => revealObserver.observe(element));

const sectionLinks = new Map(
  [...document.querySelectorAll(".section-nav a")].map((link) => [
    link.getAttribute("href").slice(1),
    link,
  ]),
);

const sectionObserver = new IntersectionObserver(
  (entries) => {
    const visible = entries
      .filter((entry) => entry.isIntersecting)
      .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];

    if (!visible) return;
    document.querySelectorAll(".section-nav a").forEach((link) => link.removeAttribute("aria-current"));
    sectionLinks.get(visible.target.id)?.setAttribute("aria-current", "true");
  },
  { rootMargin: "-25% 0px -55% 0px", threshold: [0, 0.2, 0.5] },
);

document.querySelectorAll("section[data-section]").forEach((section) => sectionObserver.observe(section));

const progressBar = document.querySelector("#page-progress-bar");
function updateProgress() {
  const scrollable = document.documentElement.scrollHeight - window.innerHeight;
  const progress = scrollable > 0 ? Math.min(window.scrollY / scrollable, 1) : 0;
  progressBar.style.transform = `scaleX(${progress})`;
}

updateProgress();
window.addEventListener("scroll", updateProgress, { passive: true });
window.addEventListener("resize", updateProgress);
