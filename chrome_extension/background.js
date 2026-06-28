const ORGS_URL = "https://claude.ai/api/organizations";
const BRIDGE_URL = "http://localhost:9876/usage";

async function fetchAndSend() {
  try {
    const orgsRes = await fetch(ORGS_URL, { credentials: "include" });
    if (!orgsRes.ok) return;
    const orgs = await orgsRes.json();
    const orgId = orgs?.[0]?.uuid;
    if (!orgId) return;

    const usageRes = await fetch(`${ORGS_URL}/${orgId}/usage`, { credentials: "include" });
    if (!usageRes.ok) return;
    const data = await usageRes.json();

    await fetch(BRIDGE_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
  } catch (_) {
    // trayアプリが起動していない場合は無視
  }
}

chrome.alarms.create("fetchUsage", { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "fetchUsage") fetchAndSend();
});

fetchAndSend();
