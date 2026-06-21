import express from "express";
import path from "path";
import crypto from "crypto";
import { createServer as createViteServer } from "vite";

interface User {
  user_id: string; // UUID string
  username: string; // String max 100
  email: string; // String max 255
  passwordHash: string;
  created_at: string;
  updated_at: string;
}

// In-Memory User Database
const USERS_DB: Map<string, User> = new Map();

// Generate high quality UUID
function generateUUID(): string {
  return crypto.randomUUID();
}

const JWT_SECRET = process.env.JWT_SECRET || "sciparser_super_secret_signature_key_2026_!";

// Cryptographic token helpers matching standard JWT logic
function generateJWT(payload: any): string {
  const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url");
  const encodedPayload = Buffer.from(JSON.stringify(payload)).toString("base64url");
  const signature = crypto.createHmac("sha256", JWT_SECRET).update(`${header}.${encodedPayload}`).digest("base64url");
  return `${header}.${encodedPayload}.${signature}`;
}

function verifyJWT(token: string): any {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const [header, encodedPayload, signature] = parts;
    const expectedSignature = crypto.createHmac("sha256", JWT_SECRET).update(`${header}.${encodedPayload}`).digest("base64url");
    if (signature !== expectedSignature) return null;
    return JSON.parse(Buffer.from(encodedPayload, "base64url").toString("utf8"));
  } catch {
    return null;
  }
}

// Demo user removed - users must sign up to log in

async function startServer() {
  const app = express();
  const PORT = 3000;

  // Body Parsing Middleware
  app.use(express.json());

  // API - Sign Up
  // Endpoint path is "/sciparser/v1/singup" (retaining the exact typo 'singup' requested)
  app.post("/sciparser/v1/singup", (req, res) => {
    const { username, password, email } = req.body;

    if (!username || !password || !email) {
      return res.status(400).json({ error: "username, password, and email are required" });
    }

    // Basic email validation
    if (!email.includes("@")) {
      return res.status(400).json({ error: "Please enter a valid email address" });
    }

    // Check if username already exists
    if (USERS_DB.has(username.toLowerCase())) {
      return res.status(400).json({ error: "Username already taken" });
    }

    // Check if email already registered
    let emailExists = false;
    for (const u of USERS_DB.values()) {
      if (u.email.toLowerCase() === email.toLowerCase()) {
        emailExists = true;
        break;
      }
    }

    if (emailExists) {
      return res.status(400).json({ error: "Email already registered" });
    }

    // Create user
    const userId = generateUUID();
    const timestamp = new Date().toISOString();
    const newUser: User = {
      user_id: userId,
      username: username,
      email: email,
      passwordHash: crypto.createHash("sha256").update(password).digest("hex"),
      created_at: timestamp,
      updated_at: timestamp,
    };

    USERS_DB.set(username.toLowerCase(), newUser);

    console.log(`User created: ${username} (ID: ${userId})`);

    return res.status(200).json({
      username: newUser.username,
      password: null, // As requested in the schema of signup response
      email: newUser.email,
    });
  });

  // API - Sign In
  app.post("/sciparser/v1/signin", (req, res) => {
    const { username, password } = req.body;

    if (!username || !password) {
      return res.status(400).json({ error: "username and password are required" });
    }

    const user = USERS_DB.get(username.toLowerCase());
    if (!user) {
      return res.status(400).json({ error: "Incorrect email or password" });
    }

    const calculatedHash = crypto.createHash("sha256").update(password).digest("hex");
    if (user.passwordHash !== calculatedHash) {
      return res.status(400).json({ error: "Incorrect email or password" });
    }

    // Generate Bearer JWT Token containing user_id and username
    const token = generateJWT({
      user_id: user.user_id,
      username: user.username,
    });

    return res.status(200).json({
      access_token: token,
      token_type: "bearer"
    });
  });

  // API - Current Session User Info (Decodes from Authorization Bearer header)
  app.get("/api/me", (req, res) => {
    const authHeader = req.headers.authorization;
    if (!authHeader || !authHeader.startsWith("Bearer ")) {
      return res.status(401).json({ error: "Unauthorized access" });
    }

    const token = authHeader.split(" ")[1];
    const claims = verifyJWT(token);

    if (!claims) {
      return res.status(401).json({ error: "Invalid token" });
    }

    // Look up the database to get real fields
    let matchedUser: User | null = null;
    for (const u of USERS_DB.values()) {
      if (u.user_id === claims.user_id) {
        matchedUser = u;
        break;
      }
    }

    if (!matchedUser) {
      return res.status(404).json({ error: "User session not found in database" });
    }

    return res.status(200).json({
      user: {
        user_id: matchedUser.user_id,
        username: matchedUser.username,
        email: matchedUser.email,
        created_at: matchedUser.created_at,
        updated_at: matchedUser.updated_at,
      }
    });
  });

  // In-memory Playwright Playmaker Browser Simulator State
  interface SimulatedElement {
    type: string;
    text?: string;
    title?: string;
    authors?: string;
    desc?: string;
    link?: string;
  }

  interface SimulatedSite {
    title: string;
    content: string;
    citations: string[];
    elements: SimulatedElement[];
  }

  const SIMULATED_SITES: Record<string, SimulatedSite> = {
    "arxiv": {
      title: "[2403.11985] SciParser: Deep Document Formatting on Heterogeneous PDFs",
      content: "We present SciParser, a state-of-the-art layout parser custom trained on multi-column academic PDF structures. Traditional rule-based crawlers fail to capture flow hierarchies...",
      citations: [
        "Vaswani et al. (2017) 'Attention is All You Need'",
        "Beltagy et al. (2019) 'SciBERT: A Pretrained Language Model for Scientific Text'"
      ],
      elements: [
        { type: "header", text: "arXiv:2403.11985v1 [cs.DL] 18 Mar 2026" },
        { type: "title", text: "SciParser: Deep Document Formatting on Heterogeneous Research PDFs" },
        { type: "authors", text: "Dhayalan P., Krishnaswamy R., et al. (SciERA Research)" },
        { type: "abstract_heading", text: "Abstract" },
        { type: "abstract", text: "Accurate text extraction and metadata alignment from PDF layout continues to be a bottleneck for scientific workflow engines. Present systems struggle with tables and nested formulas..." },
        { type: "section", title: "1. Introduction", text: "Scientific publishing templates vary wildly across publishers (IEEE, ACM, Springer). Converting these to clean JSON requires a multi-stage semantic parser..." }
      ]
    },
    "pubmed": {
      title: "PubMed Central: Advanced Molecular Bio-Extraction Pipeline",
      content: "Recent developments in natural language processing (NLP) for biological sciences demand clean text corpora. Playwright-driven bio-parsers offer reliable structured streams...",
      citations: [
        "Smith et al. (2021) 'BioNLP and Molecular Entities Extraction'",
        "Johnson et al. (2023) 'High-throughput PubMed Parsing'"
      ],
      elements: [
        { type: "header", text: "PMC ID: PMC1038291 || Published Online April 2026" },
        { type: "title", text: "Deep Bio-Extraction Pipeline and Entity Linkage" },
        { type: "authors", text: "Saraswathi A., Dhayalan P. (BioSci Division)" },
        { type: "abstract_heading", text: "Abstract" },
        { type: "abstract", text: "Modern biomedical literature is expanding exponentially. Extracting biochemical relationships requires dynamic crawlers that load interactive widgets on PMC web articles." }
      ]
    },
    "google": {
      title: "Google Scholar search: 'SciParser pdf structure alignment'",
      content: "Showing top 3 articles for SciParser deep document layout parsers. Relevance scores calculated based on citation networks.",
      citations: [
        "SciParser Core Release v2 (2025)",
        "Multi-Column Citation Extractors (2024)"
      ],
      elements: [
        { type: "search_result", title: "SciParser: A deep learning system for scientific document parsing", desc: "Dhayalan P - SciERA Technical Reports, 2025 - arXiv.org...", link: "https://arxiv.org/abs/2403.11985" },
        { type: "search_result", title: "High-fidelity citation graphs via headless browsers", desc: "Senthil K, Dhayalan P - Journal of Digital Libraries, 2026...", link: "https://scholar.google.com/citations" }
      ]
    }
  };

  interface BrowserSession {
    isActive: boolean;
    url: string;
    status: "idle" | "launching" | "navigating" | "extracting" | "completed" | "error";
    logs: string[];
    stepsCount: number;
    siteKey: string;
  }

  let BROWSER_SESSION: BrowserSession = {
    isActive: false,
    url: "",
    status: "idle",
    logs: [],
    stepsCount: 0,
    siteKey: "arxiv"
  };

  function getSiteSpec(url: string): { key: string; spec: SimulatedSite } {
    const norm = url.toLowerCase();
    if (norm.includes("pubmed") || norm.includes("pmc") || norm.includes("nih.gov")) {
      return { key: "pubmed", spec: SIMULATED_SITES.pubmed };
    }
    if (norm.includes("scholar") || norm.includes("google") || norm.includes("search")) {
      return { key: "google", spec: SIMULATED_SITES.google };
    }
    return { key: "arxiv", spec: SIMULATED_SITES.arxiv };
  }

  let simulationTimer1: NodeJS.Timeout | null = null;
  let simulationTimer2: NodeJS.Timeout | null = null;
  let simulationTimer3: NodeJS.Timeout | null = null;

  function triggerBrowserSimulation(url: string) {
    if (simulationTimer1) clearTimeout(simulationTimer1);
    if (simulationTimer2) clearTimeout(simulationTimer2);
    if (simulationTimer3) clearTimeout(simulationTimer3);

    const { key, spec } = getSiteSpec(url);

    BROWSER_SESSION.isActive = true;
    BROWSER_SESSION.url = url;
    BROWSER_SESSION.status = "launching";
    BROWSER_SESSION.siteKey = key;
    BROWSER_SESSION.logs = [
      `[${new Date().toLocaleTimeString()}] [Playwright] Initializing isolated headless Chromium browser context...`,
      `[${new Date().toLocaleTimeString()}] [Playwright] chromium.launch({ headless: true, args: ["--no-sandbox", "--disable-gpu"] })`,
      `[${new Date().toLocaleTimeString()}] [Playwright] Browser launched successfully. Session ID: ps_${Math.random().toString(36).substring(3, 9)}`
    ];
    BROWSER_SESSION.stepsCount = 1;

    const delay = 1500;

    simulationTimer1 = setTimeout(() => {
      BROWSER_SESSION.status = "navigating";
      BROWSER_SESSION.logs.push(
        `[${new Date().toLocaleTimeString()}] [Playwright] Creating secure incognito browser context...`,
        `[${new Date().toLocaleTimeString()}] [Playwright] page.goto("${url}", { waitUntil: "domcontentloaded", timeout: 15000 })`,
        `[${new Date().toLocaleTimeString()}] [Playwright] Web socket connection established for real-time frame streaming...`
      );
      BROWSER_SESSION.stepsCount = 2;
    }, delay * 1);

    simulationTimer2 = setTimeout(() => {
      BROWSER_SESSION.status = "extracting";
      BROWSER_SESSION.logs.push(
        `[${new Date().toLocaleTimeString()}] [Playwright] Page loaded successfully. Page Title: "${spec.title}"`,
        `[${new Date().toLocaleTimeString()}] [Playwright] Capturing layout frame 01. Size: 1280x850`,
        `[${new Date().toLocaleTimeString()}] [Playwright] Injecting abstract and citations scraper hooks...`,
        `[${new Date().toLocaleTimeString()}] [Playwright] Locating primary PDF content references and bibliography nodes...`
      );
      BROWSER_SESSION.stepsCount = 3;
    }, delay * 2.5);

    simulationTimer3 = setTimeout(() => {
      BROWSER_SESSION.status = "completed";
      BROWSER_SESSION.logs.push(
        `[${new Date().toLocaleTimeString()}] [Playwright] Extraction complete! Successfully harvested layout blocks.`,
        `[${new Date().toLocaleTimeString()}] [Playwright] Found ${spec.elements.length} document layouts and ${spec.citations.length} academic references.`,
        `[${new Date().toLocaleTimeString()}] [Playwright] Transferring JSON metadata packet to SciParser pipeline...`,
        `[${new Date().toLocaleTimeString()}] [Playwright] page.close()`,
        `[${new Date().toLocaleTimeString()}] [Playwright] Browser context safe exit.`
      );
      BROWSER_SESSION.stepsCount = 4;
    }, delay * 4);
  }

  // API - Get active browser session state
  app.get("/api/browser-state", (req, res) => {
    return res.status(200).json({ 
      session: BROWSER_SESSION,
      sites: SIMULATED_SITES
    });
  });

  // API - Toggle browser active state manually
  app.post("/api/browser-state/toggle", (req, res) => {
    const { active, url } = req.body;
    BROWSER_SESSION.isActive = typeof active === "boolean" ? active : !BROWSER_SESSION.isActive;
    if (BROWSER_SESSION.isActive) {
      const targetUrl = url || BROWSER_SESSION.url || "https://arxiv.org/abs/2403.11985";
      triggerBrowserSimulation(targetUrl);
    } else {
      BROWSER_SESSION.status = "idle";
    }
    return res.status(200).json({ session: BROWSER_SESSION });
  });

  // API - Clear browser session logs
  app.post("/api/browser-state/clear", (req, res) => {
    BROWSER_SESSION.isActive = false;
    BROWSER_SESSION.status = "idle";
    BROWSER_SESSION.logs = [];
    BROWSER_SESSION.url = "";
    return res.status(200).json({ session: BROWSER_SESSION });
  });

  // In-memory tracking for session uploads and conversations
  const SESSION_UPLOADS: Array<{ id: string; name: string; size: number; type: string; uploadedAt: string }> = [];
  const SESSION_MESSAGES: Array<{ id: string; role: 'user' | 'assistant'; content: string; timestamp: string; files?: string[] }> = [];

  // API - Get Uploaded Files
  app.get("/api/uploads", (req, res) => {
    return res.status(200).json({ uploads: SESSION_UPLOADS });
  });

  // API - Upload file (JSON metadata exchange)
  app.post("/api/upload", (req, res) => {
    const { name, size, type } = req.body;
    if (!name) {
      return res.status(400).json({ error: "File name is required" });
    }
    const newUpload = {
      id: generateUUID(),
      name,
      size: size || 1024 * 342, // size in bytes
      type: type || "application/pdf",
      uploadedAt: new Date().toISOString()
    };
    SESSION_UPLOADS.push(newUpload);
    return res.status(200).json({ success: true, file: newUpload });
  });

  // API - Get Conversations
  app.get("/api/chat", (req, res) => {
    return res.status(200).json({ messages: SESSION_MESSAGES });
  });

  // API - Send query and fetch response stream block
  app.post("/api/chat", (req, res) => {
    const { content, files, preferLiveBrowser } = req.body;
    if (!content) {
      return res.status(400).json({ error: "Message content constraint violation" });
    }

    const userMsg = {
      id: generateUUID(),
      role: 'user' as const,
      content,
      files: files || [],
      timestamp: new Date().toISOString()
    };
    SESSION_MESSAGES.push(userMsg);

    // AI / SciParser heuristic parsing responses
    let text = "";
    const prompt = content.toLowerCase();

    // Check for demo request explicitly first to showcase Playwright Browser
    if (prompt.includes("demo")) {
      const demoUrl = "https://arxiv.org/abs/2403.11985";
      triggerBrowserSimulation(demoUrl);
      BROWSER_SESSION.isActive = true;
      text = `### 🌐 SciParser Playwright Browser Demo Mode Activated!

I have launched a live, isolated **Playwright headless crawler** for you in split-screen mode on the right side of your page.

#### 🛠️ How to Activate and Use the Playwright Browser:

1. **Integrated Toolbar Control (Header):**
   We have simplified the controls into **one single, high-contrast button** in the header. Look at the top right:
   * **Inactive State:** Displays **Playwright Browser** with a gray indicator dot.
   * **Active State:** Displays **Browser is Live** with a pulsating green indicator dot signaling that the headless crawler is active and streaming live viewport buffers. Click it anytime to toggle the split-screen panel on/off.

2. **Triggering via Chat (Auto-Activation):**
   Simply type or paste *any scientific URL* (arXiv, PubMed, or Google Scholar) directly into the chat prompt. SciParser will recognize the domain, boot a Playwright instance, and load the webpage frame-by-frame on your right.

3. **In-Page Interactive Address Bar:**
   Inside the split-screen view on the right, you can manually type or paste URLs directly into the **Live Location Address Bar** and press enter. The Playwright instance will instantly dispatch navigation in real-time.

4. **Real-time Terminal Logs:**
   At the bottom-right of the active browser screen, you will find the **Terminal Console**. This streams raw standard output logs ('stdout') directly from Playwright API hook dispatches.

*Give it a try right now! Look at the browser window to see the ArXiv abstract parsing details in real-time or check the terminal logs.*`;
    } else {
      // Check if the user message contains a URL or requests headless crawler activity
      const urlRegex = /(https?:\/\/[^\s]+|www\.[^\s]+|[a-zA-Z0-9-]+\.(edu|org|com|gov|net)[^\s]*)/i;
      const match = content.match(urlRegex);
      let extractedUrl = "";

      if (match) {
        extractedUrl = match[0];
        if (!extractedUrl.startsWith("http")) {
          extractedUrl = "https://" + extractedUrl;
        }
      } else if (prompt.includes("browser") || prompt.includes("crawl") || prompt.includes("scrape") || prompt.includes("playwright")) {
        extractedUrl = "https://arxiv.org/abs/2403.11985";
      }

      const isLiveBrowserMode = preferLiveBrowser !== false;

      if (extractedUrl) {
        if (isLiveBrowserMode) {
          triggerBrowserSimulation(extractedUrl);
          text = `[SciParser Headless Extraction] 🌐 Playwright Browser started to crawl ${extractedUrl}!\n\nI am loading the page, capturing the frame buffers, and parsing layout metadata in split-screen mode on your right. Ready to parse abstract, citations, and content blocks.`;
        } else {
          // Deactivate browser state automatically
          BROWSER_SESSION.isActive = false;
          text = `[SciParser Text-Only Ingestion] 📥 URL ${extractedUrl} ingested successfully!\n\nI have parsed the text elements directly from the source metadata engine. (Live split-screen Playwright rendering is currently turned off based on your preference. To see visual page captures and CSS layout selectors, please turn the "Live Browser" toggle back ON).`;
        }
      } else if (prompt.includes("help") || prompt.includes("how")) {
        text = "To get started, drop any scientific research PDF, enter a Doi address, or paste/enter website URLs (like an arXiv link). I can instantly initiate a real-time Playwright-powered metadata crawler and display the browser frames side-by-side!";
      } else if (prompt.includes("parse") || prompt.includes("extract")) {
        text = "Successfully initiated SciParser PDF extraction model. Extracted 12 scientific entities. Schema matching: [Confidence: 98.6%, Keywords: 'Deep Learning', 'Neural Net', 'Spatio-Temporal']. No visual layout discrepancies found.";
      } else if (prompt.includes("hello") || prompt.includes("hi")) {
        text = "Greetings! Welcome to SciParser Portal. Paste a URL or ask me to browse a paper, and watch the background Playwright browser stream visual elements live!";
      } else {
        text = `Received and logged payload: "${content}". SciParser core neural engine has ingested this query and mapped it against current model vectors. Let me know if you would like me to output structured references!`;
      }
    }

    const assistantMsg = {
      id: generateUUID(),
      role: 'assistant' as const,
      content: text,
      timestamp: new Date().toISOString()
    };
    SESSION_MESSAGES.push(assistantMsg);

    return res.status(200).json({
      userMessage: userMsg,
      assistantMessage: assistantMsg
    });
  });

  // Serve static UI assets or fallback to Vite middleware
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Server running on http://localhost:${PORT}`);
  });
}

startServer();
