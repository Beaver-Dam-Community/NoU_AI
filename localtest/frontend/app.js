const API = '/api';
let isChatMode = false;

// ── 페이지 라우팅 ──────────────────────────
function navigateTo(page) {
  document.querySelectorAll('.page').forEach(p => p.classList.add('hidden'));
  document.getElementById(`page-${page}`).classList.remove('hidden');
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const nav = document.querySelector(`[data-page="${page}"]`);
  if (nav) nav.classList.add('active');
  if (page === 'saved') loadHistoryList();
}

// ── 사이드바 ───────────────────────────────
document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', e => {
    e.preventDefault();
    const page = item.dataset.page;
    if (page === 'home') resetHome();
    else if (page) navigateTo(page);
  });
});

function resetHome() {
  // 채팅 모드 해제
  isChatMode = false;
  const homeEl = document.getElementById('page-home');
  homeEl.classList.remove('chat-mode');

  // 스레드 비우기
  document.getElementById('chat-thread').innerHTML = '';

  // 초기 UI 복원
  document.getElementById('home-intro').classList.remove('hidden');
  document.getElementById('suggestions').classList.remove('hidden');
  document.getElementById('chat-disclaimer').classList.add('hidden');

  // 헤더 제목 숨기기
  const titleEl = document.getElementById('header-chat-title');
  titleEl.textContent = '';
  titleEl.classList.remove('visible');

  // 입력창 초기화
  input.value = '';
  input.style.height = 'auto';
  updateSendBtn();

  navigateTo('home');
}

// ── 탭 전환 ────────────────────────────────
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
  });
});

// ── 추천 프롬프트 칩 ───────────────────────
document.querySelectorAll('.suggestion-chip').forEach(chip => {
  chip.addEventListener('click', () => {
    input.value = chip.dataset.prompt;
    autoResize();
    updateSendBtn();
    input.focus();
  });
});

// ── 파일 첨부 ──────────────────────────────
const fileInput = document.getElementById('file-input');
document.getElementById('btn-attach').addEventListener('click', () => fileInput.click());

let attachedFile = null;
fileInput.addEventListener('change', () => {
  attachedFile = fileInput.files[0] || null;
  const btn = document.getElementById('btn-attach');
  btn.textContent = attachedFile ? '📎' : '＋';
  btn.title = attachedFile ? `첨부: ${attachedFile.name}` : '파일 첨부';
});

// ── 입력창 ─────────────────────────────────
const input = document.getElementById('chat-input');
const sendBtn = document.getElementById('btn-send');

function autoResize() {
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 200) + 'px';
}

function updateSendBtn() {
  sendBtn.style.background = input.value.trim() ? '#1a1a1a' : '#d0cbc5';
}

input.addEventListener('input', () => {
  autoResize();
  updateSendBtn();
});

input.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

sendBtn.addEventListener('click', sendMessage);

// ── 채팅 모드 전환 ─────────────────────────
function enterChatMode(firstMsg) {
  if (isChatMode) return;
  isChatMode = true;

  // 로고·탭·추천칩 숨기기
  document.getElementById('home-intro').classList.add('hidden');
  document.getElementById('suggestions').classList.add('hidden');
  document.getElementById('chat-disclaimer').classList.remove('hidden');

  // 메인에 chat-mode 클래스 → 레이아웃 전환
  document.getElementById('page-home').classList.add('chat-mode');

  // 헤더에 제목 표시
  const titleEl = document.getElementById('header-chat-title');
  titleEl.textContent = firstMsg.length > 30 ? firstMsg.slice(0, 30) + '…' : firstMsg;
  titleEl.classList.add('visible');

  // 날짜 구분선 삽입
  const today = new Date().toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric' });
  const divider = document.createElement('div');
  divider.className = 'date-divider';
  divider.textContent = today;
  document.getElementById('chat-thread').appendChild(divider);
}

// ── 메시지 렌더링 ──────────────────────────
function appendMessage(role, text) {
  const thread = document.getElementById('chat-thread');
  const div = document.createElement('div');
  div.className = `message message--${role}`;
  div.textContent = text;
  thread.appendChild(div);
  thread.scrollTop = thread.scrollHeight;
  return div;
}

// ── 전송 ───────────────────────────────────
async function sendMessage() {
  const msg = input.value.trim();
  if (!msg) return;

  const model = document.getElementById('model-select').value;

  // 첫 메시지일 때 화면 전환
  enterChatMode(msg);

  appendMessage('user', msg);
  input.value = '';
  input.style.height = 'auto';
  updateSendBtn();
  input.disabled = true;
  sendBtn.disabled = true;

  const thinking = appendMessage('assistant', '...');
  thinking.classList.add('message--loading');

  // 스크롤
  const thread = document.getElementById('chat-thread');
  thread.scrollTop = thread.scrollHeight;

  try {
    const res = await fetch(`${API}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: msg, model }),
    });
    if (!res.ok) throw new Error(`서버 오류: ${res.status}`);
    const data = await res.json();
    thinking.classList.remove('message--loading');

    // 역공격 응답이면 시각적으로 구분
    if (data.is_counter_attack) {
      thinking.classList.add('message--counter-attack');
      thinking.innerHTML = '';

      // 배지
      const badge = document.createElement('div');
      badge.className = 'counter-attack-badge';
      badge.textContent = 'COUNTER-ATTACK';
      thinking.appendChild(badge);

      // 상세 정보
      const info = document.createElement('div');
      info.className = 'counter-attack-info';
      info.textContent = `Strategy: ${data.strategy || 'unknown'} | Category: ${data.attack_category || 'unknown'} | Blocked by: ${data.blocked_by || 'unknown'}`;
      thinking.appendChild(info);

      // 역공격 응답 본문
      const body = document.createElement('div');
      body.className = 'counter-attack-body';
      body.textContent = data.reply;
      thinking.appendChild(body);
    } else {
      thinking.textContent = data.reply;
    }
  } catch (err) {
    thinking.classList.remove('message--loading');
    thinking.textContent = `오류가 발생했습니다: ${err.message}`;
  } finally {
    input.disabled = false;
    sendBtn.disabled = false;
    input.focus();
    attachedFile = null;
    fileInput.value = '';
    document.getElementById('btn-attach').textContent = '＋';
    document.getElementById('btn-attach').title = '파일 첨부';
    thread.scrollTop = thread.scrollHeight;
  }
}

// ── 히스토리 ───────────────────────────────
async function loadHistoryList() {
  const listEl = document.getElementById('history-list');
  listEl.innerHTML = '<p class="history-empty">불러오는 중...</p>';
  try {
    const res = await fetch(`${API}/history`);
    const data = await res.json();
    if (data.dates.length === 0) {
      listEl.innerHTML = '<p class="history-empty">저장된 대화가 없습니다.</p>';
      return;
    }
    listEl.innerHTML = '';
    data.dates.forEach(date => {
      const btn = document.createElement('button');
      btn.className = 'history-date-btn';
      btn.textContent = date;
      btn.addEventListener('click', () => loadHistoryContent(date, btn));
      listEl.appendChild(btn);
    });
  } catch {
    listEl.innerHTML = '<p class="history-empty">불러오기 실패</p>';
  }
}

async function loadHistoryContent(date, activeBtn) {
  document.querySelectorAll('.history-date-btn').forEach(b => b.classList.remove('active'));
  activeBtn.classList.add('active');
  const placeholder = document.getElementById('history-placeholder');
  const contentEl = document.getElementById('history-content');
  placeholder.classList.add('hidden');
  contentEl.classList.remove('hidden');
  contentEl.textContent = '불러오는 중...';
  try {
    const res = await fetch(`${API}/history/${date}`);
    if (!res.ok) throw new Error();
    contentEl.textContent = await res.text();
  } catch {
    contentEl.textContent = '내용을 불러올 수 없습니다.';
  }
}

navigateTo('home');
