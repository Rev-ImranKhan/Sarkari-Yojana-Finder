// script.js
// Frontend logic: PDF upload (drag-drop + click), document list refresh,
// and chat (send question -> show "Thinking..." -> render grounded answer).

const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const uploadStatus = document.getElementById("uploadStatus");
const docList = document.getElementById("docList");
const docCount = document.getElementById("docCount");

const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const chatScroll = document.getElementById("chatScroll");
const sendBtn = document.getElementById("sendBtn");

// ---------------------------------------------------------------------
// Document list
// ---------------------------------------------------------------------
async function refreshDocuments() {
  try {
    const res = await fetch("/documents");
    const data = await res.json();
    const docs = data.documents || [];

    docCount.textContent = `${docs.length} document${docs.length === 1 ? "" : "s"} loaded`;

    if (docs.length === 0) {
      docList.innerHTML = `<li class="doc-empty">Abhi koi document upload nahi hua.</li>`;
      return;
    }

    docList.innerHTML = docs.map(d => `<li>${escapeHtml(d)}</li>`).join("");
  } catch (err) {
    console.error("Documents fetch fail:", err);
  }
}

// ---------------------------------------------------------------------
// Upload (drag-drop + click)
// ---------------------------------------------------------------------
dropzone.addEventListener("click", (e) => {
  // label+hidden input already triggers click, this guard avoids double-open
});

["dragenter", "dragover"].forEach(evt => {
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });
});

["dragleave", "drop"].forEach(evt => {
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
  });
});

dropzone.addEventListener("drop", (e) => {
  const file = e.dataTransfer.files[0];
  if (file) uploadFile(file);
});

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  if (file) uploadFile(file);
});

async function uploadFile(file) {
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    setUploadStatus("Sirf PDF files allowed hain.", "err");
    return;
  }

  setUploadStatus(`'${file.name}' upload ho raha hai...`, "pending");

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("/upload", { method: "POST", body: formData });
    const data = await res.json();

    if (!res.ok) {
      setUploadStatus(data.error || "Upload fail hua.", "err");
      return;
    }

    setUploadStatus(data.message, "ok");
    refreshDocuments();
  } catch (err) {
    setUploadStatus("Server se connect nahi ho paya.", "err");
  } finally {
    fileInput.value = "";
  }
}

function setUploadStatus(text, kind) {
  uploadStatus.textContent = text;
  uploadStatus.className = `upload-status ${kind}`;
}

// ---------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------
chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = chatInput.value.trim();
  if (!question) return;

  addMessage("user", question);
  chatInput.value = "";
  sendBtn.disabled = true;

  const thinkingEl = addThinkingBubble();

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const data = await res.json();

    thinkingEl.remove();

    if (!res.ok) {
      addMessage("bot", data.error || "Kuch gadbad ho gayi.");
    } else {
      addMessage("bot", data.answer, data.sources);
    }
  } catch (err) {
    thinkingEl.remove();
    addMessage("bot", "Server se connect nahi ho paya. Kya Flask app chal raha hai?");
  } finally {
    sendBtn.disabled = false;
    chatInput.focus();
  }
});

function addMessage(role, text, sources) {
  const wrap = document.createElement("div");
  wrap.className = `msg msg-${role}`;

  const avatar = document.createElement("div");
  avatar.className = `msg-avatar ${role === "bot" ? "bot-avatar" : "user-avatar"}`;
  avatar.textContent = role === "bot" ? "S" : "U";

  const bubbleWrap = document.createElement("div");

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";
  bubble.textContent = text;
  bubbleWrap.appendChild(bubble);

  if (sources && sources.length > 0) {
    const src = document.createElement("div");
    src.className = "msg-sources";
    src.innerHTML = "Source: " + sources.map(s => `<span>${escapeHtml(s)}</span>`).join("");
    bubbleWrap.appendChild(src);
  }

  wrap.appendChild(avatar);
  wrap.appendChild(bubbleWrap);
  chatScroll.appendChild(wrap);
  chatScroll.scrollTop = chatScroll.scrollHeight;
  return wrap;
}

function addThinkingBubble() {
  const wrap = document.createElement("div");
  wrap.className = "msg msg-bot thinking";
  wrap.innerHTML = `
    <div class="msg-avatar bot-avatar">S</div>
    <div class="msg-bubble">
      <span class="dot"></span><span class="dot"></span><span class="dot"></span>
    </div>
  `;
  chatScroll.appendChild(wrap);
  chatScroll.scrollTop = chatScroll.scrollHeight;
  return wrap;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// initial load
refreshDocuments();
