const https = require("https");
const GITHUB_TOKEN = process.env.REPO_TOKEN;
const GITHUB_OWNER = process.env.GITHUB_OWNER || "chriswjohnston";
const GITHUB_REPO  = process.env.GITHUB_REPO  || "chriswjohnston-site";
const FILE_PATH    = "subscribers.json";

function githubRequest(method, path, body) {
  return new Promise((resolve, reject) => {
    const data = body ? JSON.stringify(body) : null;
    const req = https.request({
      hostname: "api.github.com", path, method,
      headers: {
        "Authorization": `Bearer ${GITHUB_TOKEN}`,
        "User-Agent": "chriswjohnston-site",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github.v3+json",
        ...(data ? { "Content-Length": Buffer.byteLength(data) } : {}),
      },
    }, (res) => {
      let chunks = "";
      res.on("data", c => chunks += c);
      res.on("end", () => {
        try { resolve({ status: res.statusCode, body: JSON.parse(chunks) }); }
        catch(e) { resolve({ status: res.statusCode, body: chunks }); }
      });
    });
    req.on("error", reject);
    if (data) req.write(data);
    req.end();
  });
}

exports.handler = async (event) => {
  const headers = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Content-Type": "application/json",
  };
  if (event.httpMethod === "OPTIONS") return { statusCode: 204, headers, body: "" };
  if (event.httpMethod !== "POST") return { statusCode: 405, headers, body: JSON.stringify({ error: "Method not allowed" }) };

  let email;
  try { ({ email } = JSON.parse(event.body)); }
  catch { return { statusCode: 400, headers, body: JSON.stringify({ error: "Invalid JSON" }) }; }

  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))
    return { statusCode: 400, headers, body: JSON.stringify({ error: "Invalid email" }) };

  email = email.toLowerCase().trim();
  if (!GITHUB_TOKEN) return { statusCode: 500, headers, body: JSON.stringify({ error: "Server error" }) };

  const getResp = await githubRequest("GET", `/repos/${GITHUB_OWNER}/${GITHUB_REPO}/contents/${FILE_PATH}`);
  let subscribers = { subscribers: [] }, sha = null;
  if (getResp.status === 200) {
    try {
      const decoded = Buffer.from(getResp.body.content, "base64").toString("utf8");
      subscribers = JSON.parse(decoded);
      sha = getResp.body.sha;
    } catch { subscribers = { subscribers: [] }; }
  }

  const existing = subscribers.subscribers || [];
  if (existing.some(s => (typeof s === "string" ? s : s.email) === email))
    return { statusCode: 200, headers, body: JSON.stringify({ message: "Already subscribed" }) };

  subscribers.subscribers = [...existing, { email, subscribed_at: new Date().toISOString() }];
  const content = Buffer.from(JSON.stringify(subscribers, null, 2)).toString("base64");
  const putResp = await githubRequest("PUT",
    `/repos/${GITHUB_OWNER}/${GITHUB_REPO}/contents/${FILE_PATH}`,
    { message: "Add subscriber", content, ...(sha ? { sha } : {}) }
  );

  if (putResp.status === 200 || putResp.status === 201)
    return { statusCode: 200, headers, body: JSON.stringify({ message: "Subscribed!" }) };
  return { statusCode: 500, headers, body: JSON.stringify({ error: "Failed to save" }) };
};
