// ==UserScript==
// @name         fnpalayer
// @namespace    http://tampermonkey.net/
// @author       wuyu123
// @match        *://*/v/movie/*
// @match        *://*/v/tv/episode/*
// @match        *://*/v/tv/season/*
// @grant        GM_xmlhttpRequest
// @connect      127.0.0.1
// ==/UserScript==

(function () {
  console.log("fnpalyer脚本开始运行...");

  const PUSH_URL = "http://127.0.0.1:8080/push";
  const KEY = "/NAS 的文件/";
  const VIDEO_EXT = /\.(mkv|mp4|avi|mov|m4v|ts|flv|wmv)$/i;

  let isSending = false;

  function extractPathFromTitle(title) {
    title = (title || "").trim();
    if (!title.includes(KEY)) return null;

    const idxKey = title.indexOf(KEY);
    const headIdx = title.lastIndexOf("存储空间", idxKey);
    let path = (headIdx >= 0 ? title.slice(headIdx) : title.slice(idxKey)).trim();

    const m = path.match(/^(.*?\.(mkv|mp4|avi|mov|m4v|ts|flv|wmv))/i);
    if (!m) return null;

    path = m[1].trim();
    if (!VIDEO_EXT.test(path)) return null;
    return path;
  }

  function pushToFlask(payload) {
    return new Promise((resolve, reject) => {
      GM_xmlhttpRequest({
        method: "POST",
        url: PUSH_URL,
        headers: { "Content-Type": "application/json" },
        data: JSON.stringify(payload),
        onload: (res) => resolve(res),
        onerror: (e) => reject(e),
      });
    });
  }

  function findFirstMatch(root = document) {
    const nodes = root.querySelectorAll(".select-text[title]");
    console.log("扫描到 .select-text[title] 数量:", nodes.length);

    for (const el of nodes) {
      const title = el.getAttribute("title") || "";
      const path = extractPathFromTitle(title);
      if (!path) continue;
      return { title, path };
    }
    return null;
  }

  function toast(msg) {
    const t = document.createElement("div");
    t.textContent = msg;
    t.style.cssText = [
      "position:fixed",
      "right:16px",
      "bottom:70px",
      "z-index:999999",
      "background:rgba(0,0,0,0.75)",
      "color:#fff",
      "padding:8px 10px",
      "border-radius:8px",
      "font-size:12px",
      "max-width:60vw",
      "white-space:pre-wrap",
    ].join(";");
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 2500);
  }

  function createPotplayButton() {
    const container = document.querySelector("div.relative.flex.h-\\[54px\\].shrink-0.items-center.gap-2");
    if (!container) return false;

    // 已经存在就不重复插入
    if (container.querySelector("[data-tm-potplay-btn='1']")) return true;

    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = "potplay";
    btn.setAttribute("data-tm-potplay-btn", "1");

    btn.style.cssText = [
      "height:54px",
      "min-width:120px",
      "padding:0 16px",
      "border-radius:9999px",
      "border:1px solid rgba(0,0,0,0.12)",
      "background:var(--semi-color-primary, #1677ff)",
      "color:#fff",
      "font-size:18px",
      "line-height:54px",
      "cursor:pointer",
      "display:inline-flex",
      "align-items:center",
      "justify-content:center",
      "gap:8px",
      "user-select:none",
    ].join(";");

    btn.addEventListener("click", async () => {
      if (isSending) return;
      isSending = true;
      const oldText = btn.textContent;
      btn.textContent = "扫描中...";

      try {
        const match = findFirstMatch(document);
        if (!match) {
          toast("未找到可用的 NAS 路径");
          btn.textContent = oldText;
          return;
        }

        btn.textContent = "发送中...";
        const res = await pushToFlask({
          title: match.title,
          path: match.path,
          page_url: location.href,
        });

        console.log("push ok:", res.status, res.responseText);
        toast("已发送 ✅");
        btn.textContent = "potplay ✅";
        setTimeout(() => (btn.textContent = oldText), 2000);
      } catch (e) {
        console.log("push error:", e);
        toast("发送失败 ❌（看 Console）");
        btn.textContent = oldText;
      } finally {
        isSending = false;
      }
    });

    // 插入到播放按钮后面
    const firstChild = container.firstElementChild;
    if (firstChild && firstChild.nextSibling) container.insertBefore(btn, firstChild.nextSibling);
    else container.appendChild(btn);

    console.log("已插入 potplay 按钮");
    return true;
  }

  // =========================
  // 新增：周期扫描 + 保活
  // =========================

  // 1) 高频扫描：直到按钮插入成功（或超时）
  const fastIntervalMs = 500;
  const fastMaxMs = 30_000; // 30秒超时（可调）
  const fastStart = Date.now();

  const fastTimer = setInterval(() => {
    const ok = createPotplayButton();
    if (ok) {
      clearInterval(fastTimer);
      console.log("potplay 按钮插入成功，进入保活扫描。");
      startKeepAlive();
      return;
    }
    if (Date.now() - fastStart > fastMaxMs) {
      clearInterval(fastTimer);
      console.log("fast scan 超时，进入保活扫描（低频）。");
      startKeepAlive();
    }
  }, fastIntervalMs);

  // 2) 低频保活：防止 SPA 重绘把按钮弄没了
  let keepAliveTimer = null;
  function startKeepAlive() {
    if (keepAliveTimer) return;
    keepAliveTimer = setInterval(() => {
      createPotplayButton(); // 如果被删了会重新插
    }, 3000);
  }

  // 3) 路由变化时（pushState/replaceState/popstate）再触发一次快速扫描
  function hookHistory() {
    const _pushState = history.pushState;
    const _replaceState = history.replaceState;

    history.pushState = function () {
      const r = _pushState.apply(this, arguments);
      // 触发一次尽快插入
      setTimeout(createPotplayButton, 50);
      return r;
    };
    history.replaceState = function () {
      const r = _replaceState.apply(this, arguments);
      setTimeout(createPotplayButton, 50);
      return r;
    };
    window.addEventListener("popstate", () => setTimeout(createPotplayButton, 50));
  }
  hookHistory();
})();