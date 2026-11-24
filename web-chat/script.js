const CHANNEL_NAME = "lan_web_chat_v1";
const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB
const AVATAR_COLORS = [
  "#6366f1", "#ec4899", "#14b8a6", "#f59e0b",
  "#8b5cf6", "#06b6d4", "#ef4444", "#10b981"
];

const channel = new BroadcastChannel(CHANNEL_NAME);

const state = {
  me: null,
  peers: new Map(),           // peerId -> { id, name, color, status }
  activeRoom: "general",      // "general" hoặc DM roomId
  activePeerId: null,
  messages: { general: [] },  // roomId -> Message[]
  unread: {},                 // roomId -> count
  typingPeers: new Map(),     // peerId -> { name, timeout }
  searchQuery: ""
};

// DOM elements
const loginModal = document.getElementById("loginModal");
const loginForm = document.getElementById("loginForm");
const usernameInput = document.getElementById("usernameInput");
const themeToggle = document.getElementById("themeToggle");
const peerSearch = document.getElementById("peerSearch");
const peerList = document.getElementById("peerList");
const peerCount = document.getElementById("peerCount");
const roomList = document.getElementById("roomList");
const meAvatar = document.getElementById("meAvatar");
const meName = document.getElementById("meName");
const statusToggle = document.getElementById("statusToggle");
const meStatusText = document.getElementById("meStatusText");
const activeAvatar = document.getElementById("activeAvatar");
const activeTitle = document.getElementById("activeTitle");
const activeSubtitle = document.getElementById("activeSubtitle");
const messagesContainer = document.getElementById("messagesContainer");
const typingIndicator = document.getElementById("typingIndicator");
const messageForm = document.getElementById("messageForm");
const messageInput = document.getElementById("messageInput");
const attachBtn = document.getElementById("attachBtn");
const fileInput = document.getElementById("fileInput");
const emojiBtn = document.getElementById("emojiBtn");
const emojiPicker = document.getElementById("emojiPicker");
const clearChatBtn = document.getElementById("clearChatBtn");
const dropZone = document.getElementById("dropZone");
const dropOverlay = document.getElementById("dropOverlay");

// Tiện ích
const generateId = () =>
  crypto.randomUUID ? crypto.randomUUID() : "u_" + Math.random().toString(36).slice(2, 10);

const getDmRoomId = (idA, idB) => [idA, idB].sort().join("__");

const escapeHtml = (str = "") =>
  str.replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[ch]));

const formatTime = (ts) =>
  new Date(ts).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });

const formatFileSize = (bytes) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
};

const getInitial = (name) => name.trim().charAt(0).toUpperCase() || "?";

// Đăng nhập
loginForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const name = usernameInput.value.trim();
  if (!name) return;

  state.me = {
    id: generateId(),
    name,
    color: AVATAR_COLORS[Math.floor(Math.random() * AVATAR_COLORS.length)],
    status: "online"
  };

  meAvatar.textContent = getInitial(name);
  meAvatar.style.background = state.me.color;
  meName.textContent = name;
  loginModal.classList.add("hidden");
  messageInput.focus();

  channel.postMessage({ type: "HELLO", peer: state.me });
});

// Đổi giao diện Sáng / Tối
themeToggle.addEventListener("click", () => {
  const isLight = document.body.classList.toggle("light");
  themeToggle.textContent = isLight ? "🌙" : "☀️";
});

// Đổi trạng thái Online / Away
statusToggle.addEventListener("click", () => {
  if (!state.me) return;
  state.me.status = state.me.status === "online" ? "away" : "online";
  statusToggle.className = `status-pill ${state.me.status}`;
  meStatusText.textContent = state.me.status === "online" ? "Online" : "Away";
  channel.postMessage({ type: "STATUS", peer: state.me });
});

// Tìm kiếm người dùng
peerSearch.addEventListener("input", (e) => {
  state.searchQuery = e.target.value.trim().toLowerCase();
  renderPeers();
});

// Chọn phòng chung
roomList.querySelector('[data-room="general"]').addEventListener("click", () => {
  switchRoom("general", null);
});

// Xóa màn hình tin nhắn hiện tại
clearChatBtn.addEventListener("click", () => {
  state.messages[state.activeRoom] = [];
  renderMessages();
});

// Chuyển phòng chat
function switchRoom(roomId, peerId) {
  state.activeRoom = roomId;
  state.activePeerId = peerId;
  state.unread[roomId] = 0;

  document.querySelectorAll(".chat-item").forEach((el) => el.classList.remove("active"));

  if (roomId === "general") {
    roomList.querySelector('[data-room="general"]').classList.add("active");
    activeAvatar.className = "avatar channel-avatar";
    activeAvatar.style.background = "";
    activeAvatar.textContent = "#";
    activeTitle.textContent = "Phòng chung";
    activeSubtitle.textContent = "Trò chuyện cùng tất cả thành viên đang mở";
  } else {
    const peer = state.peers.get(peerId);
    if (peer) {
      activeAvatar.className = "avatar";
      activeAvatar.style.background = peer.color;
      activeAvatar.textContent = getInitial(peer.name);
      activeTitle.textContent = peer.name;
      activeSubtitle.textContent = peer.status === "online" ? "Đang hoạt động" : "Tạm vắng (Away)";
    }
  }

  renderPeers();
  updateGeneralBadge();
  renderMessages();
  renderTyping();
  messageInput.focus();
}

// Hiển thị danh sách người online
function renderPeers() {
  const peers = Array.from(state.peers.values()).filter((p) =>
    p.name.toLowerCase().includes(state.searchQuery)
  );
  peerCount.textContent = state.peers.size;

  if (peers.length === 0) {
    peerList.innerHTML = `<li class="empty-peers">${
      state.peers.size === 0 ? "Mở thêm 1 tab nữa để chat 2 chiều!" : "Không tìm thấy người dùng"
    }</li>`;
    return;
  }

  peerList.innerHTML = "";
  peers.forEach((peer) => {
    const dmRoomId = getDmRoomId(state.me.id, peer.id);
    const unread = state.unread[dmRoomId] || 0;
    const isActive = state.activeRoom === dmRoomId;

    const li = document.createElement("li");
    li.className = `chat-item ${isActive ? "active" : ""}`;
    li.innerHTML = `
      <div class="avatar" style="background: ${peer.color}">
        ${escapeHtml(getInitial(peer.name))}
        <span class="dot-indicator ${peer.status}"></span>
      </div>
      <div class="chat-item-info">
        <div class="chat-item-name">${escapeHtml(peer.name)}</div>
        <div class="chat-item-sub">${peer.status === "online" ? "Online" : "Away"}</div>
      </div>
      <span class="unread-badge ${unread ? "" : "hidden"}">${unread}</span>
    `;
    li.addEventListener("click", () => switchRoom(dmRoomId, peer.id));
    peerList.appendChild(li);
  });
}

function updateGeneralBadge() {
  const badge = document.getElementById("badge-general");
  const count = state.unread.general || 0;
  badge.textContent = count;
  badge.classList.toggle("hidden", count === 0);
}

// Render tin nhắn
function renderMessages() {
  const list = state.messages[state.activeRoom] || [];
  messagesContainer.innerHTML = "";

  if (list.length === 0) {
    messagesContainer.innerHTML = `<div class="system-notice">Chưa có tin nhắn nào. Hãy bắt đầu cuộc trò chuyện!</div>`;
    return;
  }

  list.forEach((msg) => {
    if (msg.system) {
      const div = document.createElement("div");
      div.className = "system-notice";
      div.textContent = msg.text;
      messagesContainer.appendChild(div);
      return;
    }

    const isMe = state.me && msg.senderId === state.me.id;
    const row = document.createElement("div");
    row.className = `msg-row ${isMe ? "me" : "other"}`;

    let contentHtml = "";
    if (msg.text) {
      contentHtml += `<div>${escapeHtml(msg.text)}</div>`;
    }
    if (msg.file) {
      if (msg.file.type.startsWith("image/")) {
        contentHtml += `
          <a href="${msg.file.dataUrl}" download="${escapeHtml(msg.file.name)}">
            <img class="msg-image" src="${msg.file.dataUrl}" alt="${escapeHtml(msg.file.name)}" />
          </a>
        `;
      } else {
        contentHtml += `
          <a class="file-card" href="${msg.file.dataUrl}" download="${escapeHtml(msg.file.name)}">
            <span>📄</span>
            <div>
              <div class="file-name">${escapeHtml(msg.file.name)}</div>
              <div class="file-size">${formatFileSize(msg.file.size)} · Nhấn để tải</div>
            </div>
          </a>
        `;
      }
    }

    row.innerHTML = `
      <div class="msg-meta">${isMe ? "Bạn" : escapeHtml(msg.senderName)} · ${formatTime(msg.timestamp)}</div>
      <div class="msg-bubble">${contentHtml}</div>
    `;
    messagesContainer.appendChild(row);
  });

  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Gửi tin nhắn văn bản hoặc file
function sendMessage({ text = "", file = null }) {
  if (!state.me || (!text && !file)) return;

  const message = {
    id: generateId(),
    senderId: state.me.id,
    senderName: state.me.name,
    text,
    file,
    timestamp: Date.now()
  };

  pushMessage(state.activeRoom, message);
  channel.postMessage({
    type: "MESSAGE",
    roomId: state.activeRoom,
    targetId: state.activePeerId,
    message
  });
}

function pushMessage(roomId, message) {
  if (!state.messages[roomId]) state.messages[roomId] = [];
  state.messages[roomId].push(message);

  if (roomId === state.activeRoom) {
    renderMessages();
  } else {
    state.unread[roomId] = (state.unread[roomId] || 0) + 1;
    if (roomId === "general") updateGeneralBadge();
    else renderPeers();
  }
}

messageForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = messageInput.value.trim();
  if (!text) return;
  sendMessage({ text });
  messageInput.value = "";
  emojiPicker.classList.add("hidden");
  broadcastTyping(false);
});

// Xử lý file đính kèm & kéo thả
function handleFile(file) {
  if (!file) return;
  if (file.size > MAX_FILE_SIZE) {
    alert("File vượt quá giới hạn 5MB.");
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    sendMessage({
      file: {
        name: file.name,
        size: file.size,
        type: file.type || "application/octet-stream",
        dataUrl: reader.result
      }
    });
  };
  reader.readAsDataURL(file);
}

attachBtn.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => {
  handleFile(fileInput.files[0]);
  fileInput.value = "";
});

["dragenter", "dragover"].forEach((evt) =>
  dropZone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropOverlay.classList.remove("hidden");
  })
);
["dragleave", "drop"].forEach((evt) =>
  dropZone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropOverlay.classList.add("hidden");
  })
);
dropZone.addEventListener("drop", (e) => handleFile(e.dataTransfer.files[0]));

// Emoji picker
emojiBtn.addEventListener("click", () => emojiPicker.classList.toggle("hidden"));
emojiPicker.addEventListener("click", (e) => {
  if (e.target.tagName === "SPAN") {
    messageInput.value += e.target.textContent;
    messageInput.focus();
  }
});

// Trạng thái "đang nhập..."
let typingTimer = null;
function broadcastTyping(isTyping) {
  if (!state.me) return;
  channel.postMessage({
    type: "TYPING",
    roomId: state.activeRoom,
    peerId: state.me.id,
    name: state.me.name,
    isTyping
  });
}

messageInput.addEventListener("input", () => {
  broadcastTyping(true);
  clearTimeout(typingTimer);
  typingTimer = setTimeout(() => broadcastTyping(false), 1200);
});

function renderTyping() {
  const names = Array.from(state.typingPeers.values())
    .filter((t) => t.roomId === state.activeRoom)
    .map((t) => t.name);

  if (names.length === 0) {
    typingIndicator.classList.add("hidden");
  } else {
    typingIndicator.textContent = `${names.join(", ")} đang nhập tin nhắn...`;
    typingIndicator.classList.remove("hidden");
  }
}

// Lắng nghe sự kiện từ các tab khác
channel.onmessage = (event) => {
  const data = event.data;
  if (!state.me || !data) return;

  switch (data.type) {
    case "HELLO":
      if (data.peer.id === state.me.id) return;
      state.peers.set(data.peer.id, data.peer);
      renderPeers();
      pushMessage("general", { system: true, text: `${data.peer.name} vừa tham gia phòng chat` });
      channel.postMessage({ type: "WELCOME", peer: state.me, targetId: data.peer.id });
      break;

    case "WELCOME":
      if (data.targetId !== state.me.id) return;
      state.peers.set(data.peer.id, data.peer);
      renderPeers();
      break;

    case "STATUS":
      if (state.peers.has(data.peer.id)) {
        state.peers.set(data.peer.id, data.peer);
        renderPeers();
        if (state.activePeerId === data.peer.id) {
          activeSubtitle.textContent =
            data.peer.status === "online" ? "Đang hoạt động" : "Tạm vắng (Away)";
        }
      }
      break;

    case "LEAVE":
      if (state.peers.has(data.peerId)) {
        const leftPeer = state.peers.get(data.peerId);
        state.peers.delete(data.peerId);
        renderPeers();
        pushMessage("general", { system: true, text: `${leftPeer.name} đã rời khỏi phòng chat` });
      }
      break;

    case "MESSAGE":
      if (data.roomId === "general" || data.targetId === state.me.id) {
        pushMessage(data.roomId, data.message);
      }
      break;

    case "TYPING":
      if (data.peerId === state.me.id) return;
      if (data.isTyping) {
        clearTimeout(state.typingPeers.get(data.peerId)?.timeout);
        const timeout = setTimeout(() => {
          state.typingPeers.delete(data.peerId);
          renderTyping();
        }, 2000);
        state.typingPeers.set(data.peerId, { name: data.name, roomId: data.roomId, timeout });
      } else {
        state.typingPeers.delete(data.peerId);
      }
      renderTyping();
      break;
  }
};

window.addEventListener("beforeunload", () => {
  if (state.me) {
    channel.postMessage({ type: "LEAVE", peerId: state.me.id });
  }
});