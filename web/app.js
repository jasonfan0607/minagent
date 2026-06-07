const sessionInput = document.querySelector('#sessionInput');
const messageInput = document.querySelector('#messageInput');
const sendButton = document.querySelector('#sendButton');
const refreshButton = document.querySelector('#refreshButton');
const statusText = document.querySelector('#statusText');
const messagesEl = document.querySelector('#messages');
const tracesEl = document.querySelector('#traces');
const tasksEl = document.querySelector('#tasks');
const messageCountEl = document.querySelector('#messageCount');
const traceCountEl = document.querySelector('#traceCount');
const toolCountEl = document.querySelector('#toolCount');
const taskCountEl = document.querySelector('#taskCount');
const lastAnswerEl = document.querySelector('#lastAnswer');
const messageTemplate = document.querySelector('#messageTemplate');
const traceTemplate = document.querySelector('#traceTemplate');

const formatJson = (value) => JSON.stringify(value, null, 2);

const formatTime = (ts) => {
  if (!ts) return 'unknown time';
  return new Date(ts * 1000).toLocaleTimeString('zh-CN', { hour12: false });
};

const summarizeTrace = (trace) => {
  if (trace.error) return trace.error;
  if (trace.kind === 'tool') {
    const status = trace.ok ? '执行成功' : '执行失败';
    return `${trace.tool || 'unknown'} · ${status}`;
  }
  const action = trace.action || {};
  if (action.type === 'tool') return `LLM 请求调用工具：${action.tool}`;
  if (action.type === 'final') return `LLM 输出最终答案`;
  return 'LLM 返回动作 JSON';
};

const setEmpty = (element, text) => {
  element.className = element.className.split(' ').filter((item) => item !== 'empty-state').join(' ');
  element.innerHTML = '';
  element.classList.add('empty-state');
  element.textContent = text;
};

const clearContainer = (element) => {
  element.classList.remove('empty-state');
  element.innerHTML = '';
};

const renderMessages = (messages) => {
  if (!messages.length) {
    setEmpty(messagesEl, '暂无对话，发送一条消息开始。');
    return;
  }

  clearContainer(messagesEl);
  messages.forEach((message) => {
    const node = messageTemplate.content.cloneNode(true);
    const card = node.querySelector('.message-card');
    card.classList.add(message.role === 'user' ? 'user' : 'assistant');
    node.querySelector('header').textContent = message.role === 'user' ? 'USER INPUT' : 'AGENT ANSWER';
    node.querySelector('p').textContent = message.content || '';
    messagesEl.appendChild(node);
  });
};

const renderTraces = (traces) => {
  if (!traces.length) {
    setEmpty(tracesEl, '暂无 trace');
    return;
  }

  clearContainer(tracesEl);
  traces.forEach((trace) => {
    const node = traceTemplate.content.cloneNode(true);
    const card = node.querySelector('.trace-card');
    const title = trace.kind === 'tool' ? `STEP ${trace.step} · TOOL` : `STEP ${trace.step} · LLM`;
    card.classList.add(trace.kind === 'tool' ? 'tool' : 'llm');
    if (trace.error || trace.ok === false) card.classList.add('error');
    node.querySelector('strong').textContent = title;
    node.querySelector('span').textContent = formatTime(trace.ts);
    node.querySelector('.trace-summary').textContent = summarizeTrace(trace);
    node.querySelector('pre').textContent = formatJson(trace);
    tracesEl.appendChild(node);
  });
};

const renderTasks = (tasks) => {
  const list = Object.values(tasks || {});
  if (!list.length) {
    setEmpty(tasksEl, '暂无任务');
    return;
  }

  clearContainer(tasksEl);
  list.forEach((task) => {
    const item = document.createElement('article');
    item.className = 'task';
    const notes = Array.isArray(task.notes) && task.notes.length ? ` · ${task.notes.at(-1)}` : '';
    item.innerHTML = `<strong></strong><span></span>`;
    item.querySelector('strong').textContent = task.title || task.id;
    item.querySelector('span').textContent = `${task.status || 'unknown'} · ${task.id}${notes}`;
    tasksEl.appendChild(item);
  });
};

const renderSession = (data) => {
  if (!data.ok) throw new Error(data.error || '请求失败');
  const session = data.session || {};
  const messages = session.messages || [];
  const traces = session.traces || [];
  const tasks = session.tasks || {};
  const latestAssistant = [...messages].reverse().find((message) => message.role === 'assistant');

  renderMessages(messages);
  renderTraces(traces);
  renderTasks(tasks);
  messageCountEl.textContent = messages.length;
  traceCountEl.textContent = traces.length;
  toolCountEl.textContent = traces.filter((trace) => trace.kind === 'tool').length;
  taskCountEl.textContent = Object.keys(tasks).length;
  lastAnswerEl.textContent = latestAssistant ? '已生成回复' : '等待输入';
  statusText.textContent = '在线';
};

const loadSession = async () => {
  statusText.textContent = '同步中';
  const response = await fetch(`/api/session?id=${encodeURIComponent(sessionInput.value || 'default')}`);
  renderSession(await response.json());
};

const sendMessage = async () => {
  const message = messageInput.value.trim();
  if (!message) return;

  sendButton.disabled = true;
  statusText.textContent = '运行中';
  lastAnswerEl.textContent = 'Agent 思考中';

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionInput.value || 'default', message }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error_type ? `${data.error_type}: ${data.error || '请求失败'}` : data.error || '请求失败');
    }
    renderSession(data);
    messageInput.value = '';
  } catch (error) {
    statusText.textContent = '异常';
    lastAnswerEl.textContent = error.message;
  } finally {
    sendButton.disabled = false;
  }
};

sendButton.addEventListener('click', sendMessage);
refreshButton.addEventListener('click', loadSession);
sessionInput.addEventListener('change', loadSession);
messageInput.addEventListener('keydown', (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
    sendMessage();
  }
});

loadSession().catch((error) => {
  statusText.textContent = '异常';
  lastAnswerEl.textContent = error.message;
});
