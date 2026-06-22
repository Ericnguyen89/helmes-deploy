#!/usr/bin/env node
/**
 * Puppeteer browser helper for Helmes Agent.
 *
 * Invoked as a subprocess by agent/plugins/browser_tool.py. Reads a JSON job
 * from stdin, drives a headless Chromium session through a sequence of actions,
 * and prints a JSON result to stdout. Always emits valid JSON (even on error)
 * so the Python side can parse deterministically.
 *
 * Input (stdin JSON):
 *   {
 *     "url": "https://...",                 // required: page to open
 *     "actions": [                          // optional: steps before extracting
 *       {"type": "wait_for", "selector": "#x"},
 *       {"type": "click", "selector": "button.login"},
 *       {"type": "type", "selector": "#q", "text": "hello"},
 *       {"type": "wait", "ms": 1000},
 *       {"type": "evaluate", "script": "document.title"}
 *     ],
 *     "screenshot": false,                  // optional: capture PNG
 *     "screenshotPath": "/workspace/shot.png",
 *     "fullPage": false,
 *     "extractText": true,                  // optional: return rendered text
 *     "timeout": 30000,                     // optional: per-op timeout (ms)
 *     "userAgent": "..."                    // optional
 *   }
 *
 * Output (stdout JSON):
 *   { "ok": true, "title", "url", "text", "actionResults": [...], "screenshot", "error": null }
 */

const puppeteer = require("puppeteer-core");

const EXECUTABLE_PATH =
  process.env.PUPPETEER_EXECUTABLE_PATH || process.env.CHROMIUM_PATH || "/usr/bin/chromium";
const MAX_TEXT = 60000;
const DEFAULT_UA =
  "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";

function readStdin() {
  return new Promise((resolve, reject) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (c) => (data += c));
    process.stdin.on("end", () => resolve(data));
    process.stdin.on("error", reject);
  });
}

async function runActions(page, actions, timeout, results) {
  for (const a of actions) {
    const type = (a.type || "").toLowerCase();
    switch (type) {
      case "goto":
        await page.goto(a.url, { waitUntil: "networkidle2", timeout });
        results.push(`goto: ${a.url}`);
        break;
      case "click":
        await page.waitForSelector(a.selector, { timeout });
        await page.click(a.selector);
        results.push(`click: ${a.selector}`);
        break;
      case "type":
        await page.waitForSelector(a.selector, { timeout });
        await page.type(a.selector, a.text != null ? String(a.text) : "");
        results.push(`type into ${a.selector}`);
        break;
      case "wait_for":
      case "waitforselector":
        await page.waitForSelector(a.selector, { timeout });
        results.push(`wait_for: ${a.selector}`);
        break;
      case "wait":
        await new Promise((r) => setTimeout(r, Math.min(a.ms || 1000, timeout)));
        results.push(`wait: ${a.ms || 1000}ms`);
        break;
      case "press":
        await page.keyboard.press(a.key || "Enter");
        results.push(`press: ${a.key || "Enter"}`);
        break;
      case "evaluate": {
        const out = await page.evaluate((s) => {
          // eslint-disable-next-line no-eval
          const v = eval(s);
          return v === undefined ? null : v;
        }, a.script);
        results.push(`evaluate -> ${JSON.stringify(out)?.slice(0, 1000)}`);
        break;
      }
      default:
        results.push(`unknown action: ${type}`);
    }
  }
}

async function main() {
  const raw = await readStdin();
  let job;
  try {
    job = JSON.parse(raw || "{}");
  } catch (e) {
    process.stdout.write(JSON.stringify({ ok: false, error: `Invalid input JSON: ${e.message}` }));
    process.exit(1);
    return;
  }

  const timeout = Math.max(5000, Math.min(job.timeout || 30000, 120000));
  const out = { ok: false, title: null, url: null, text: null, actionResults: [], screenshot: null, error: null };
  let browser;

  try {
    browser = await puppeteer.launch({
      executablePath: EXECUTABLE_PATH,
      headless: "new",
      args: [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--no-zygote",
        "--disable-extensions",
      ],
    });
    const page = await browser.newPage();
    await page.setUserAgent(job.userAgent || DEFAULT_UA);
    await page.setViewport({ width: 1280, height: 900 });
    page.setDefaultTimeout(timeout);
    page.setDefaultNavigationTimeout(timeout);

    if (job.url) {
      await page.goto(job.url, { waitUntil: "networkidle2", timeout });
      out.actionResults.push(`opened: ${job.url}`);
    }

    if (Array.isArray(job.actions) && job.actions.length) {
      await runActions(page, job.actions, timeout, out.actionResults);
    }

    out.title = await page.title();
    out.url = page.url();

    if (job.extractText !== false) {
      const text = await page.evaluate(() => document.body ? document.body.innerText : "");
      out.text = (text || "").slice(0, MAX_TEXT);
    }

    if (job.screenshot && job.screenshotPath) {
      await page.screenshot({ path: job.screenshotPath, fullPage: !!job.fullPage });
      out.screenshot = job.screenshotPath;
    }

    out.ok = true;
  } catch (e) {
    out.error = e && e.message ? e.message : String(e);
  } finally {
    if (browser) {
      try {
        await browser.close();
      } catch (_) {}
    }
  }

  process.stdout.write(JSON.stringify(out));
  process.exit(out.ok ? 0 : 1);
}

main();
