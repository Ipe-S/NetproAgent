const API = "";  // same origin

// ── Health check ──────────────────────────────────────────────────────────────
async function checkHealth() {
  const badge = document.getElementById("status-badge");
  try {
    const res = await fetch(`${API}/api/health`);
    const data = await res.json();
    if (data.ollama?.status === "ok") {
      const model = data.ollama.models?.[0] ?? "Ollama";
      badge.textContent = `✓ ${model}`;
      badge.className = "badge badge-ok";
    } else {
      badge.textContent = "Ollama no disponible";
      badge.className = "badge badge-error";
    }
  } catch {
    badge.textContent = "Backend desconectado";
    badge.className = "badge badge-error";
  }
}

// ── Documents ─────────────────────────────────────────────────────────────────
async function loadDocuments() {
  try {
    const res = await fetch(`${API}/api/documents`);
    const data = await res.json();
    renderDocuments(data.documents, data.stats);
  } catch (e) {
    console.error("Error cargando documentos:", e);
  }
}

function renderDocuments(docs, stats) {
  const list = document.getElementById("doc-list");
  const statsEl = document.getElementById("kb-stats");

  statsEl.textContent = `${stats.total_documents} doc${stats.total_documents !== 1 ? "s" : ""} · ${stats.total_chunks} fragmentos`;

  if (!docs.length) {
    list.innerHTML = '<p class="empty-hint">No hay documentos cargados.</p>';
    return;
  }

  list.innerHTML = docs.map(doc => {
    const lower = doc.filename.toLowerCase();
    const icon = lower.endsWith(".pdf") ? "📄" : (lower.endsWith(".jpg") || lower.endsWith(".jpeg") || lower.endsWith(".png")) ? "🖼️" : "📝";
    const safeFilename = escapeHtml(doc.filename);
    return `
      <div class="doc-item" data-filename="${safeFilename}">
        <span class="doc-icon">${icon}</span>
        <div class="doc-info">
          <div class="doc-name" title="${safeFilename}">${safeFilename}</div>
          <div class="doc-meta">${doc.total_chunks} fragmento${doc.total_chunks !== 1 ? "s" : ""}</div>
        </div>
        <button class="doc-delete" onclick="deleteDocument('${safeFilename.replace(/'/g, "\\'")}')" title="Eliminar">✕</button>
      </div>`;
  }).join("");
}

async function deleteDocument(filename) {
  if (!confirm(`¿Eliminar "${filename}" de la base de conocimiento?`)) return;
  try {
    const res = await fetch(`${API}/api/documents/${encodeURIComponent(filename)}`, { method: "DELETE" });
    if (res.ok) {
      showToast(`"${filename}" eliminado`);
      loadDocuments();
    } else {
      const err = await res.json();
      showToast(err.detail || "Error al eliminar", "error");
    }
  } catch (e) {
    showToast("Error de conexión", "error");
  }
}

// ── File upload ───────────────────────────────────────────────────────────────
function handleDragOver(e) {
  e.preventDefault();
  document.getElementById("drop-zone").classList.add("drag-over");
}

function handleDragLeave(e) {
  document.getElementById("drop-zone").classList.remove("drag-over");
}

function handleDrop(e) {
  e.preventDefault();
  document.getElementById("drop-zone").classList.remove("drag-over");
  uploadFiles(Array.from(e.dataTransfer.files));
}

function handleFileSelect(e) {
  uploadFiles(Array.from(e.target.files));
  e.target.value = "";
}

async function uploadFiles(files) {
  const EXTS = [".pdf", ".md", ".jpg", ".jpeg", ".png"];
  const allowed = files.filter(f => EXTS.some(ext => f.name.toLowerCase().endsWith(ext)));
  if (!allowed.length) {
    showToast("Solo se aceptan PDF, Markdown o imágenes (JPG, PNG)", "error");
    return;
  }

  const progress = document.getElementById("upload-progress");
  const fill = document.getElementById("progress-fill");
  const label = document.getElementById("progress-label");
  progress.classList.remove("hidden");

  for (let i = 0; i < allowed.length; i++) {
    const file = allowed[i];
    label.textContent = `Procesando "${file.name}"…`;
    fill.style.width = `${((i) / allowed.length) * 100}%`;

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API}/api/documents/upload`, { method: "POST", body: formData });
      const data = await res.json();
      if (res.ok) {
        showToast(`"${file.name}" cargado (${data.chunks_created} fragmentos)`);
      } else {
        showToast(data.detail || `Error con "${file.name}"`, "error");
      }
    } catch {
      showToast(`Error subiendo "${file.name}"`, "error");
    }
  }

  fill.style.width = "100%";
  label.textContent = "¡Listo!";
  setTimeout(() => progress.classList.add("hidden"), 1200);
  loadDocuments();
}

// ── Chat ──────────────────────────────────────────────────────────────────────
let isStreaming = false;

async function sendMessage(e) {
  e.preventDefault();
  if (isStreaming) return;

  const input = document.getElementById("chat-input");
  const text = input.value.trim();
  if (!text) return;

  input.value = "";
  autoResize(input);

  appendMessage("user", text);

  const assistantEl = appendMessage("assistant", "", true);
  const bubble = assistantEl.querySelector(".message-bubble");
  bubble.classList.add("typing-cursor");

  document.getElementById("send-btn").disabled = true;
  isStreaming = true;

  try {
    const res = await fetch(`${API}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    });

    if (!res.ok) {
      const err = await res.json();
      bubble.textContent = `⚠️ ${err.detail || "Error en el servidor"}`;
      bubble.classList.remove("typing-cursor");
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let sources = [];
    let responseText = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const json = line.slice(6).trim();
        if (!json) continue;

        const msg = JSON.parse(json);
        if (msg.type === "sources") {
          sources = msg.sources;
        } else if (msg.type === "token") {
          responseText += msg.content;
          bubble.textContent = responseText;
          scrollToBottom();
        } else if (msg.type === "done") {
          bubble.classList.remove("typing-cursor");
          if (sources.length) {
            const srcEl = document.createElement("div");
            srcEl.className = "message-sources";
            srcEl.innerHTML = "Fuentes: " + sources.map(s => `<span class="source-tag">${escapeHtml(s)}</span>`).join("");
            assistantEl.appendChild(srcEl);
          }
          scrollToBottom();
        }
      }
    }
  } catch (err) {
    bubble.textContent = "⚠️ Error de conexión con el servidor.";
    bubble.classList.remove("typing-cursor");
  } finally {
    isStreaming = false;
    document.getElementById("send-btn").disabled = false;
  }
}

function appendMessage(role, text, empty = false) {
  const messages = document.getElementById("messages");
  const div = document.createElement("div");
  div.className = `message ${role}`;
  div.innerHTML = `<div class="message-bubble">${empty ? "" : escapeHtml(text)}</div>`;
  messages.appendChild(div);
  scrollToBottom();
  return div;
}

function scrollToBottom() {
  const messages = document.getElementById("messages");
  messages.scrollTop = messages.scrollHeight;
}

function handleKey(e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    document.getElementById("chat-form").dispatchEvent(new Event("submit"));
  }
}

function autoResize(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 160) + "px";
}

// ── Toast ─────────────────────────────────────────────────────────────────────
function showToast(msg, type = "success") {
  const el = document.createElement("div");
  el.style.cssText = `
    position:fixed; bottom:24px; right:24px; z-index:9999;
    background:${type === "error" ? "#7f1d1d" : "#14301f"};
    color:${type === "error" ? "#fca5a5" : "#86efac"};
    border:1px solid ${type === "error" ? "#991b1b" : "#166534"};
    padding:10px 16px; border-radius:8px; font-size:13px;
    animation:fadeIn 0.2s ease; max-width:320px; word-break:break-word;
  `;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

// ── Utils ─────────────────────────────────────────────────────────────────────
function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// ── Mode switcher ─────────────────────────────────────────────────────────────
function switchMode(mode) {
  const chatMode = document.getElementById("chat-mode");
  const clinicalMode = document.getElementById("clinical-mode");
  const tabChat = document.getElementById("tab-chat");
  const tabClinical = document.getElementById("tab-clinical");

  if (mode === "chat") {
    chatMode.classList.remove("hidden");
    clinicalMode.classList.add("hidden");
    tabChat.classList.add("active");
    tabClinical.classList.remove("active");
  } else {
    chatMode.classList.add("hidden");
    clinicalMode.classList.remove("hidden");
    tabChat.classList.remove("active");
    tabClinical.classList.add("active");
    loadClinicalStatus();
  }
}

// ── Clinical Panel ─────────────────────────────────────────────────────────────
async function saveClinicalInput(specialist) {
  const text = document.getElementById(`input-${specialist}`).value.trim();
  if (!text) { showToast("El campo no puede estar vacío", "error"); return; }

  try {
    const res = await fetch("/api/clinical/input", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ specialist, text }),
    });
    const data = await res.json();
    if (res.ok) {
      updateClinicalStatus(data.status);
      const hint = document.getElementById(`hint-${specialist}`);
      hint.classList.remove("hidden");
      setTimeout(() => hint.classList.add("hidden"), 2000);
    } else {
      showToast(data.detail || "Error al guardar", "error");
    }
  } catch {
    showToast("Error de conexión", "error");
  }
}

async function loadClinicalStatus() {
  try {
    const res = await fetch("/api/clinical/status");
    const data = await res.json();
    updateClinicalStatus(data.status);
  } catch {}
}

function updateClinicalStatus(status) {
  let allReady = true;
  for (const [key, ready] of Object.entries(status)) {
    const badge = document.getElementById(`badge-${key}`);
    if (badge) {
      badge.textContent = ready ? "✓ Listo" : "Pendiente";
      badge.className = `cl-status ${ready ? "ready" : "pending"}`;
    }
    if (!ready) allReady = false;
  }
  document.getElementById("consolidate-btn").disabled = !allReady;
}

let isClinicalStreaming = false;

async function consolidateReport() {
  if (isClinicalStreaming) return;

  const reportEl = document.getElementById("cl-report");
  reportEl.innerHTML = '<p class="cl-generating">Generando informe interdisciplinar...</p>';
  isClinicalStreaming = true;
  document.getElementById("consolidate-btn").disabled = true;
  document.getElementById("copy-report-btn").classList.add("hidden");

  try {
    const res = await fetch("/api/clinical/consolidate", { method: "POST" });
    if (!res.ok) {
      const err = await res.json();
      reportEl.innerHTML = `<p class="cl-empty">⚠️ ${escapeHtml(err.detail)}</p>`;
      return;
    }

    let fullText = "";
    reportEl.innerHTML = '<div id="cl-report-content" class="cl-report-content typing-cursor"></div>';
    const contentEl = document.getElementById("cl-report-content");

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const msg = JSON.parse(line.slice(6));
        if (msg.type === "token") {
          fullText += msg.content;
          contentEl.innerHTML = renderClinicalMarkdown(fullText);
          reportEl.scrollTop = reportEl.scrollHeight;
        } else if (msg.type === "done") {
          contentEl.classList.remove("typing-cursor");
          document.getElementById("copy-report-btn").classList.remove("hidden");
        }
      }
    }
  } catch {
    reportEl.innerHTML = '<p class="cl-empty">⚠️ Error de conexión con el servidor.</p>';
  } finally {
    isClinicalStreaming = false;
    document.getElementById("consolidate-btn").disabled = false;
  }
}

async function clearClinical() {
  if (!confirm("¿Iniciar un nuevo caso? Se borrarán todos los datos ingresados.")) return;
  try { await fetch("/api/clinical/clear", { method: "POST" }); } catch {}

  ["to", "psicologia", "neurologia"].forEach(s => {
    document.getElementById(`input-${s}`).value = "";
    document.getElementById(`hint-${s}`).classList.add("hidden");
  });
  updateClinicalStatus({ to: false, psicologia: false, neurologia: false });

  document.getElementById("cl-report").innerHTML =
    '<p class="cl-empty">El informe consolidado aparecerá aquí una vez que los tres especialistas hayan registrado sus observaciones.</p>';
  document.getElementById("copy-report-btn").classList.add("hidden");
}

function copyReport() {
  const el = document.getElementById("cl-report-content");
  if (!el) return;
  navigator.clipboard.writeText(el.innerText).then(() => showToast("Informe copiado al portapapeles"));
}

function renderClinicalMarkdown(text) {
  return text
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\n/g, "<br>");
}

// ── Init ──────────────────────────────────────────────────────────────────────
checkHealth();
loadDocuments();
setInterval(checkHealth, 30000);
