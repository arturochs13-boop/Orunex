/* Orunex Bridge - local VS Code control surface.
 *
 * The extension is deliberately dependency-free and listens only on
 * 127.0.0.1.  It exposes a small HTTP API used by the Orunex desktop agent.
 */
"use strict";

const http = require("http");
const fs = require("fs");
const os = require("os");
const path = require("path");
const crypto = require("crypto");
const { exec } = require("child_process");
const vscode = require("vscode");

const HOST = "127.0.0.1";
const BASE_PORT = 8765;
const MAX_PORT_ATTEMPTS = 12;
const CONFIG_DIR = path.join(os.homedir(), ".orunex");
const CONFIG_FILE = path.join(CONFIG_DIR, "vscode_bridge.json");

let server = null;
let activePort = null;
let token = crypto.randomBytes(24).toString("hex");
let startedAt = new Date().toISOString();

function workspaceRoot() {
  const folders = vscode.workspace.workspaceFolders || [];
  if (folders.length) return folders[0].uri.fsPath;
  return process.env.USERPROFILE || os.homedir();
}

function resolvePath(value) {
  if (!value) return workspaceRoot();
  const text = String(value).replace(/^"|"$/g, "");
  return path.isAbsolute(text) ? path.normalize(text) : path.resolve(workspaceRoot(), text);
}

function writeBridgeConfig() {
  try {
    fs.mkdirSync(CONFIG_DIR, { recursive: true });
    const folders = (vscode.workspace.workspaceFolders || []).map((folder) => folder.uri.fsPath);
    const payload = {
      port: activePort,
      token,
      pid: process.pid,
      workspaceFolders: folders,
      activeFile: vscode.window.activeTextEditor
        ? vscode.window.activeTextEditor.document.uri.fsPath
        : "",
      startedAt,
      updatedAt: new Date().toISOString(),
      extension: "orunex.orunex-bridge"
    };
    fs.writeFileSync(CONFIG_FILE, JSON.stringify(payload, null, 2), "utf8");
  } catch (error) {
    console.error("[Orunex Bridge] Could not write config:", error);
  }
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
      if (body.length > 8 * 1024 * 1024) {
        reject(new Error("Request body too large"));
        req.destroy();
      }
    });
    req.on("end", () => {
      if (!body.trim()) return resolve({});
      try {
        resolve(JSON.parse(body));
      } catch (error) {
        reject(new Error("Invalid JSON body"));
      }
    });
    req.on("error", reject);
  });
}

function json(res, status, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": Buffer.byteLength(body),
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type, X-Orunex-Token",
    "Cache-Control": "no-store"
  });
  res.end(body);
}

async function openFile(targetPath, line) {
  const resolved = resolvePath(targetPath);
  const uri = vscode.Uri.file(resolved);
  const document = await vscode.workspace.openTextDocument(uri);
  const lineIndex = Math.max(0, Number(line || 1) - 1);
  const position = new vscode.Position(Math.min(lineIndex, Math.max(0, document.lineCount - 1)), 0);
  const editor = await vscode.window.showTextDocument(document, {
    preview: false,
    preserveFocus: false,
    selection: new vscode.Range(position, position)
  });
  editor.revealRange(new vscode.Range(position, position), vscode.TextEditorRevealType.InCenterIfOutsideViewport);
  return { path: resolved, line: lineIndex + 1 };
}

async function writeFile(targetPath, content, openAfter) {
  const resolved = resolvePath(targetPath);
  const uri = vscode.Uri.file(resolved);
  const data = Buffer.from(String(content == null ? "" : content), "utf8");
  await vscode.workspace.fs.writeFile(uri, data);
  if (openAfter !== false) {
    await openFile(resolved, 1);
  }
  return { path: resolved, bytes: data.length };
}

async function replaceText(targetPath, oldText, newText) {
  const resolved = resolvePath(targetPath);
  const uri = vscode.Uri.file(resolved);
  const document = await vscode.workspace.openTextDocument(uri);
  const source = document.getText();
  const index = source.indexOf(String(oldText || ""));
  if (index < 0) {
    throw new Error("oldText was not found in " + resolved);
  }
  const edit = new vscode.WorkspaceEdit();
  edit.replace(
    uri,
    new vscode.Range(document.positionAt(index), document.positionAt(index + oldText.length)),
    String(newText == null ? "" : newText)
  );
  const applied = await vscode.workspace.applyEdit(edit);
  if (applied) await document.save();
  return { path: resolved, replaced: applied };
}

async function writeWholeDocument(targetPath, content) {
  const resolved = resolvePath(targetPath);
  const uri = vscode.Uri.file(resolved);
  const document = await vscode.workspace.openTextDocument(uri);
  const edit = new vscode.WorkspaceEdit();
  edit.replace(
    uri,
    new vscode.Range(document.positionAt(0), document.positionAt(document.getText().length)),
    String(content == null ? "" : content)
  );
  const applied = await vscode.workspace.applyEdit(edit);
  if (applied) await document.save();
  return { path: resolved, replaced: applied };
}

function getTerminal(name, cwd) {
  const wanted = String(name || "Orunex");
  let terminal = vscode.window.terminals.find((item) => item.name === wanted);
  if (!terminal) {
    terminal = vscode.window.createTerminal({
      name: wanted,
      cwd: cwd ? resolvePath(cwd) : workspaceRoot()
    });
  }
  return terminal;
}

async function runTerminal(command, cwd, name, show) {
  const terminal = getTerminal(name, cwd);
  if (show !== false) terminal.show(true);
  terminal.sendText(String(command || ""), true);
  return { terminal: terminal.name, cwd: cwd ? resolvePath(cwd) : workspaceRoot(), command: String(command || "") };
}

function execCommand(command, cwd, timeoutMs) {
  return new Promise((resolve) => {
    const started = Date.now();
    const options = {
      cwd: cwd ? resolvePath(cwd) : workspaceRoot(),
      timeout: Math.max(3000, Number(timeoutMs || 120000)),
      maxBuffer: 4 * 1024 * 1024,
      windowsHide: true,
      shell: process.env.ComSpec || "cmd.exe"
    };
    exec(String(command || ""), options, (error, stdout, stderr) => {
      resolve({
        ok: !error,
        code: error && typeof error.code === "number" ? error.code : (error ? 1 : 0),
        stdout: String(stdout || ""),
        stderr: String(stderr || ""),
        cwd: options.cwd,
        command: String(command || ""),
        durationMs: Date.now() - started
      });
    });
  });
}

async function diagnostics(targetPath) {
  const resolved = targetPath ? resolvePath(targetPath) : "";
  const all = [];
  for (const [uri, items] of vscode.languages.getDiagnostics()) {
    if (resolved && path.normalize(uri.fsPath).toLowerCase() !== path.normalize(resolved).toLowerCase()) {
      continue;
    }
    for (const item of items) {
      all.push({
        file: uri.fsPath,
        line: item.range.start.line + 1,
        column: item.range.start.character + 1,
        severity: ["error", "warning", "information", "hint"][item.severity] || "info",
        message: item.message,
        source: item.source || ""
      });
    }
  }
  return { path: resolved, diagnostics: all, count: all.length };
}

async function route(req, res) {
  if (req.method === "OPTIONS") {
    res.writeHead(204, {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, X-Orunex-Token"
    });
    return res.end();
  }

  const url = new URL(req.url, `http://${HOST}:${activePort}`);
  if (url.pathname === "/health" && req.method === "GET") {
    return json(res, 200, {
      ok: true,
      extension: "orunex.orunex-bridge",
      version: "0.1.0",
      pid: process.pid,
      port: activePort,
      workspaceFolders: (vscode.workspace.workspaceFolders || []).map((folder) => folder.uri.fsPath),
      activeFile: vscode.window.activeTextEditor ? vscode.window.activeTextEditor.document.uri.fsPath : "",
      startedAt
    });
  }

  if (url.pathname !== "/health") {
    const supplied = req.headers["x-orunex-token"];
    if (!supplied || supplied !== token) {
      return json(res, 401, { ok: false, error: "Invalid Orunex token" });
    }
  }

  if (url.pathname === "/workspace" && req.method === "GET") {
    return json(res, 200, {
      ok: true,
      workspaceFolders: (vscode.workspace.workspaceFolders || []).map((folder) => folder.uri.fsPath),
      activeFile: vscode.window.activeTextEditor ? vscode.window.activeTextEditor.document.uri.fsPath : ""
    });
  }

  if (url.pathname === "/open" && req.method === "POST") {
    const body = await readBody(req);
    return json(res, 200, { ok: true, ...(await openFile(body.path, body.line)) });
  }

  if (url.pathname === "/edit" && req.method === "POST") {
    const body = await readBody(req);
    if (body.mode === "replace") {
      return json(res, 200, { ok: true, ...(await replaceText(body.path, body.oldText, body.newText)) });
    }
    const result = body.append
      ? await (async () => {
          const resolved = resolvePath(body.path);
          let previous = "";
          try {
            previous = fs.readFileSync(resolved, "utf8");
          } catch (error) {
            previous = "";
          }
          return writeFile(resolved, previous + String(body.content || ""), body.open !== false);
        })()
      : await writeWholeDocument(body.path, body.content).catch(async (error) => {
          if (error && String(error.message || "").toLowerCase().includes("cannot open")) {
            return writeFile(body.path, body.content, body.open !== false);
          }
          throw error;
        });
    return json(res, 200, { ok: true, ...result });
  }

  if (url.pathname === "/create" && req.method === "POST") {
    const body = await readBody(req);
    return json(res, 200, { ok: true, ...(await writeFile(body.path, body.content, body.open !== false)) });
  }

  if (url.pathname === "/terminal" && req.method === "POST") {
    const body = await readBody(req);
    return json(res, 200, { ok: true, ...(await runTerminal(body.command, body.cwd, body.name, body.show)) });
  }

  if (url.pathname === "/exec" && req.method === "POST") {
    const body = await readBody(req);
    return json(res, 200, await execCommand(body.command, body.cwd, body.timeout));
  }

  if (url.pathname === "/command" && req.method === "POST") {
    const body = await readBody(req);
    const result = await vscode.commands.executeCommand(body.command, ...(body.args || []));
    return json(res, 200, { ok: true, result: result === undefined ? null : result });
  }

  if (url.pathname === "/diagnostics" && req.method === "GET") {
    return json(res, 200, { ok: true, ...(await diagnostics(url.searchParams.get("path") || "")) });
  }

  if (url.pathname === "/save" && req.method === "POST") {
    const saved = await vscode.workspace.saveAll(false);
    return json(res, 200, { ok: true, saved });
  }

  return json(res, 404, { ok: false, error: "Unknown Orunex bridge endpoint" });
}

function startServer(port, attempt) {
  const candidate = port || BASE_PORT;
  const nextAttempt = attempt || 0;
  const nextServer = http.createServer((req, res) => {
    route(req, res).catch((error) => {
      console.error("[Orunex Bridge] request failed:", error);
      json(res, 500, { ok: false, error: String(error && error.message ? error.message : error) });
    });
  });

  nextServer.on("error", (error) => {
    if (error && error.code === "EADDRINUSE" && nextAttempt < MAX_PORT_ATTEMPTS) {
      try { nextServer.close(); } catch (_) { /* noop */ }
      startServer(candidate + 1, nextAttempt + 1);
      return;
    }
    console.error("[Orunex Bridge] server error:", error);
    vscode.window.showErrorMessage("Orunex Bridge: " + String(error));
  });

  nextServer.listen(candidate, HOST, () => {
    server = nextServer;
    activePort = candidate;
    startedAt = new Date().toISOString();
    writeBridgeConfig();
    console.log(`[Orunex Bridge] listening on http://${HOST}:${activePort}`);
  });
}

function stopServer() {
  if (!server) return false;
  try {
    server.close();
  } catch (_) {
    /* noop */
  }
  server = null;
  return true;
}

function activate(context) {
  startServer(BASE_PORT, 0);

  context.subscriptions.push(
    vscode.commands.registerCommand("orunex.startBridge", () => {
      if (!server) startServer(BASE_PORT, 0);
      vscode.window.showInformationMessage("Orunex Bridge is running on port " + (activePort || BASE_PORT));
    }),
    vscode.commands.registerCommand("orunex.stopBridge", () => {
      const stopped = stopServer();
      vscode.window.showInformationMessage(stopped ? "Orunex Bridge stopped." : "Orunex Bridge was not running.");
    }),
    vscode.commands.registerCommand("orunex.showStatus", () => {
      vscode.window.showInformationMessage(
        server
          ? `Orunex Bridge: http://${HOST}:${activePort} | workspace: ${workspaceRoot()}`
          : "Orunex Bridge: stopped"
      );
    })
  );

  context.subscriptions.push({ dispose: stopServer });
  writeBridgeConfig();
}

function deactivate() {
  stopServer();
}

module.exports = { activate, deactivate };
