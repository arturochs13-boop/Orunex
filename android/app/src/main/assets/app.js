(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);

  const el = {
    app: $('app'),
    splash: $('splash'),
    pageTitle: $('pageTitle'),
    views: {
      chat: $('view-chat'),
      simplex: $('view-simplex'),
      settings: $('view-settings')
    },
    chatTitle: $('chatTitle'),
    chatSubtitle: $('chatSubtitle'),
    chatScroll: $('chatScroll'),
    emptyState: $('emptyState'),
    messageList: $('messageList'),
    suggestionGrid: document.querySelector('.suggestion-grid'),
    composerInput: $('composerInput'),
    sendButton: $('sendButton'),
    attachButton: $('attachButton'),
    modeSelect: $('modeSelect'),
    drawer: $('drawer'),
    drawerScrim: $('drawerScrim'),
    openDrawer: $('openDrawer'),
    closeDrawer: $('closeDrawer'),
    newChatButton: $('newChatButton'),
    chatList: $('chatList'),
    drawerStatus: $('drawerStatus'),
    chatMenu: $('chatMenu'),
    dialogLayer: $('dialogLayer'),
    dialogCard: $('dialogCard'),
    toast: $('toast'),
    fileInput: $('fileInput'),
    displayName: $('displayName'),
    manageMemory: $('manageMemory'),
    scaleRange: $('scaleRange'),
    scaleLabel: $('scaleLabel'),
    autoHeal: $('autoHeal'),
    saveMemory: $('saveMemory'),
    screenGlow: $('screenGlow'),
    retriesRange: $('retriesRange'),
    retriesLabel: $('retriesLabel'),
    contextRange: $('contextRange'),
    contextLabel: $('contextLabel'),
    uploadJson: $('uploadJson'),
    uploadPdf: $('uploadPdf'),
    saveSettingsButton: $('saveSettingsButton'),
    settingsFeedback: $('settingsFeedback'),
    openSimplexFromSettings: $('openSimplexFromSettings'),
    simplexStatus: $('simplexStatus'),
    simplexDetail: $('simplexDetail'),
    pairButton: $('pairButton'),
    disconnectButton: $('disconnectButton'),
    qrCard: $('qrCard'),
    qrCanvas: $('qrCanvas'),
    qrPlaceholder: $('qrPlaceholder'),
    simplexLinkBox: $('simplexLinkBox'),
    copyLinkButton: $('copyLinkButton'),
    simplexFeedback: $('simplexFeedback'),
    prefNotify: $('prefNotify'),
    prefCommands: $('prefCommands'),
    prefScreenshot: $('prefScreenshot'),
    prefRemoteScreenshot: $('prefRemoteScreenshot'),
    saveSimplexPrefs: $('saveSimplexPrefs'),
    simplexPrefsFeedback: $('simplexPrefsFeedback')
  };

  const DEFAULT_SETTINGS = {
    displayName: 'User',
    scale: 100,
    autoHeal: true,
    saveMemory: true,
    screenGlow: true,
    retries: 3,
    context: 16384,
    mode: 'Default',
    simplex: {
      paired: true,
      contact: 'Arturo_1',
      link: '',
      notify: true,
      commands: true,
      screenshot: false,
      remoteScreenshot: false
    }
  };

  const DEFAULT_CHAT = {
    id: '51cd45263901',
    title: 'Hello',
    created_at: '2026-10-21T18:09:40',
    updated_at: '2026-10-21T18:10:14',
    messages: [
      {
        role: 'user',
        text: 'hello',
        time: '2026-10-21T18:09:50'
      },
      {
        role: 'assistant',
        tag: 'Cerebro',
        text: "Hello, I'm Orunex. Central operating core. How can I help you right now?",
        time: '2026-10-21T18:09:50'
      },
      {
        role: 'user',
        text: 'What can you do?',
        time: '2026-10-21T18:10:14'
      },
      {
        role: 'assistant',
        tag: 'Cerebro',
        text: 'Error de núcleo.',
        time: '2026-10-21T18:10:14'
      }
    ]
  };

  const state = {
    chats: [],
    currentChat: null,
    settings: clone(DEFAULT_SETTINGS),
    view: 'chat',
    pendingReplyFor: null,
    filePurpose: 'attach',
    menuChatId: null,
    toastTimer: null,
    feedbackTimers: {}
  };

  const Native = window.OrunexNative || null;

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function nowIso() {
    return new Date().toISOString();
  }

  function uid() {
    const random = Math.random().toString(36).slice(2, 10);
    return `chat_${Date.now().toString(36)}_${random}`;
  }

  function nativeCall(name, ...args) {
    if (!Native || typeof Native[name] !== 'function') return null;
    try {
      return Native[name](...args);
    } catch (error) {
      console.warn('Orunex native call failed:', name, error);
      return null;
    }
  }

  function localGet(key) {
    try {
      return window.localStorage.getItem(key) || '';
    } catch (error) {
      return '';
    }
  }

  function localSet(key, value) {
    try {
      window.localStorage.setItem(key, value);
    } catch (error) {
      // Local storage is only a fallback when the native bridge is absent.
    }
  }

  const Store = {
    loadChats() {
      const value = nativeCall('loadChats');
      return value === null || value === undefined || value === ''
        ? localGet('orunex.chats.v1')
        : value;
    },
    saveChats(value) {
      nativeCall('saveChats', value);
      localSet('orunex.chats.v1', value);
    },
    loadSettings() {
      const value = nativeCall('loadSettings');
      return value === null || value === undefined || value === ''
        ? localGet('orunex.settings.v1')
        : value;
    },
    saveSettings(value) {
      nativeCall('saveSettings', value);
      localSet('orunex.settings.v1', value);
    },
    loadUi() {
      const value = nativeCall('loadUiState');
      return value === null || value === undefined || value === ''
        ? localGet('orunex.ui.v1')
        : value;
    },
    saveUi(value) {
      nativeCall('saveUiState', value);
      localSet('orunex.ui.v1', value);
    }
  };

  function parseJson(value, fallback) {
    if (!value) return fallback;
    try {
      return JSON.parse(value);
    } catch (error) {
      return fallback;
    }
  }

  function mergeSettings(raw) {
    const source = raw && typeof raw === 'object' ? raw : {};
    const simplex = Object.assign({}, DEFAULT_SETTINGS.simplex, source.simplex || {});
    const merged = Object.assign({}, DEFAULT_SETTINGS, source, { simplex });
    merged.displayName = String(merged.displayName || 'User').trim() || 'User';
    merged.scale = Number.isFinite(Number(merged.scale)) ? Number(merged.scale) : 100;
    merged.retries = Number.isFinite(Number(merged.retries)) ? Number(merged.retries) : 3;
    merged.context = Number.isFinite(Number(merged.context)) ? Number(merged.context) : 16384;
    merged.autoHeal = merged.autoHeal !== false;
    merged.saveMemory = merged.saveMemory !== false;
    merged.screenGlow = merged.screenGlow !== false;
    if (!['Default', 'Programmer', 'Deep Research', 'Agent Swapping'].includes(merged.mode)) {
      merged.mode = 'Default';
    }
    return merged;
  }

  function persistChats() {
    Store.saveChats(JSON.stringify(state.chats));
  }

  function persistSettings() {
    Store.saveSettings(JSON.stringify(state.settings));
    updateDrawerStatus();
  }

  function persistUi() {
    Store.saveUi(JSON.stringify({
      currentChatId: state.currentChat && !state.currentChat.isDraft
        ? state.currentChat.id
        : '',
      view: state.view
    }));
  }

  function mostRecentChat() {
    return state.chats
      .slice()
      .sort((a, b) => String(b.updated_at || b.created_at || '').localeCompare(
        String(a.updated_at || a.created_at || '')))
      .find(Boolean) || null;
  }

  function newDraft(focusInput) {
    state.currentChat = {
      id: uid(),
      title: 'New chat',
      created_at: nowIso(),
      updated_at: nowIso(),
      messages: [],
      isDraft: true
    };
    state.pendingReplyFor = null;
    persistUi();
    renderAll();
    closeDrawer();
    if (focusInput) {
      window.setTimeout(() => el.composerInput.focus(), 300);
    }
  }

  function ensureCurrentChat() {
    if (!state.currentChat) {
      state.currentChat = {
        id: uid(),
        title: 'New chat',
        created_at: nowIso(),
        updated_at: nowIso(),
        messages: [],
        isDraft: true
      };
    }
    return state.currentChat;
  }

  function makeTitle(text) {
    const title = String(text || '').replace(/\s+/g, ' ').trim();
    if (!title) return 'New chat';
    return title.length <= 42 ? title : `${title.slice(0, 41)}…`;
  }

  function scrollToBottom() {
    window.requestAnimationFrame(() => {
      el.chatScroll.scrollTop = el.chatScroll.scrollHeight;
    });
  }

  function renderAll() {
    renderChat();
    renderChatList();
    updateDrawerStatus();
  }

  function renderChat() {
    const chat = ensureCurrentChat();
    const messages = Array.isArray(chat.messages) ? chat.messages : [];

    el.chatTitle.textContent = chat.title || 'New chat';
    el.chatSubtitle.textContent = 'Ask Orunex anything or describe a task.';
    el.emptyState.hidden = messages.length > 0 || state.pendingReplyFor === chat.id;
    const greeting = el.emptyState.querySelector('h2');
    if (greeting) greeting.textContent = `Hello, ${state.settings.displayName || 'User'}`;

    el.messageList.replaceChildren();
    messages.forEach((message) => {
      el.messageList.appendChild(buildMessage(message));
    });

    if (state.pendingReplyFor === chat.id) {
      el.messageList.appendChild(buildTypingMessage());
    }
  }

  function buildMessage(message) {
    const row = document.createElement('div');
    const role = message.role === 'user'
      ? 'user'
      : (message.role === 'system' ? 'system' : 'assistant');
    row.className = `message ${role}`;

    if (role === 'system') {
      const label = document.createElement('span');
      label.textContent = message.text || '';
      row.appendChild(label);
      return row;
    }

    if (role === 'user') {
      const bubble = document.createElement('div');
      bubble.className = 'bubble';
      bubble.textContent = message.text || '';
      row.appendChild(bubble);
      return row;
    }

    const speaker = document.createElement('div');
    speaker.className = 'speaker';
    speaker.textContent = 'Orunex';
    row.appendChild(speaker);

    if (message.mode && message.mode !== 'Default') {
      const modeBadge = document.createElement('span');
      modeBadge.className = 'mode-badge';
      modeBadge.textContent = `✦ ${message.mode}`;
      row.appendChild(modeBadge);
    }

    const text = document.createElement('div');
    text.className = 'assistant-text';
    text.textContent = message.text || '';
    row.appendChild(text);

    if (Array.isArray(message.artifacts) && message.artifacts.length) {
      const list = document.createElement('div');
      list.className = 'artifact-list';
      message.artifacts.forEach((artifact) => list.appendChild(buildArtifactCard(artifact)));
      row.appendChild(list);
    }

    const copy = document.createElement('button');
    copy.type = 'button';
    copy.className = 'copy-button';
    copy.textContent = 'Copy';
    copy.addEventListener('click', () => copyText(message.text || ''));
    row.appendChild(copy);
    return row;
  }

  function buildTypingMessage() {
    const row = document.createElement('div');
    row.className = 'message assistant';
    const speaker = document.createElement('div');
    speaker.className = 'speaker';
    speaker.textContent = 'Orunex';
    row.appendChild(speaker);
    const thinking = document.createElement('div');
    thinking.className = 'thinking';
    thinking.setAttribute('role', 'status');
    thinking.setAttribute('aria-live', 'polite');
    thinking.innerHTML = [
      '<span class="thinking-text-wrap">',
      '<span class="thinking-glow" aria-hidden="true">Thinking...</span>',
      '<span class="thinking-text">Thinking...</span>',
      '</span>'
    ].join('');
    row.appendChild(thinking);
    return row;
  }

  function renderChatList() {
    const activeId = state.currentChat && !state.currentChat.isDraft
      ? state.currentChat.id
      : '';
    const chats = state.chats
      .slice()
      .sort((a, b) => String(b.updated_at || b.created_at || '').localeCompare(
        String(a.updated_at || a.created_at || '')));

    el.chatList.replaceChildren();

    chats.forEach((chat) => {
      const row = document.createElement('div');
      row.className = 'chat-row' + (chat.id === activeId ? ' is-active' : '');
      row.setAttribute('role', 'button');
      row.setAttribute('tabindex', '0');

      const title = document.createElement('span');
      title.className = 'chat-title';
      title.textContent = chat.title || 'New chat';
      row.appendChild(title);

      const more = document.createElement('button');
      more.type = 'button';
      more.className = 'chat-more';
      more.setAttribute('aria-label', `Options for ${chat.title || 'chat'}`);
      more.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="5" r="1.7"/><circle cx="12" cy="12" r="1.7"/><circle cx="12" cy="19" r="1.7"/></svg>';
      more.addEventListener('click', (event) => {
        event.stopPropagation();
        openChatMenu(chat.id, more);
      });
      row.appendChild(more);

      row.addEventListener('click', () => openChat(chat));
      row.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          openChat(chat);
        }
      });
      el.chatList.appendChild(row);
    });
  }

  function openChat(chat) {
    state.currentChat = chat;
    state.pendingReplyFor = null;
    state.view = 'chat';
    applyView();
    renderAll();
    persistUi();
    closeDrawer();
    scrollToBottom();
  }

  function updateDrawerStatus() {
    const paired = !!state.settings.simplex.paired;
    el.drawerStatus.classList.toggle('is-offline', !paired);
    el.drawerStatus.innerHTML = `<i></i><span>Simplex · ${paired ? 'Paired' : 'Offline'}</span>`;
  }

  function applyView() {
    Object.entries(el.views).forEach(([name, view]) => {
      const active = name === state.view;
      view.hidden = !active;
      view.classList.toggle('is-active', active);
    });

    const titles = {
      chat: 'Chat',
      simplex: 'Simplex Bridge',
      settings: 'Settings'
    };
    el.pageTitle.textContent = titles[state.view] || 'Chat';

    document.querySelectorAll('.nav-button[data-view]').forEach((button) => {
      button.classList.toggle('is-active', button.dataset.view === state.view);
    });

    if (state.view === 'simplex') syncSimplexUi();
    if (state.view === 'settings') syncSettingsUi();
  }

  function setView(name, options = {}) {
    if (!Object.prototype.hasOwnProperty.call(el.views, name)) return;
    state.view = name;
    applyView();
    if (name === 'chat') scrollToBottom();
    if (options.persist !== false) persistUi();
    closeDrawer();
  }

  function openDrawer() {
    closeChatMenu();
    el.drawer.classList.add('is-open');
    el.drawerScrim.classList.add('is-open');
    el.drawer.setAttribute('aria-hidden', 'false');
    el.chatList.scrollTop = 0;
  }

  function closeDrawer() {
    el.drawer.classList.remove('is-open');
    el.drawerScrim.classList.remove('is-open');
    el.drawer.setAttribute('aria-hidden', 'true');
  }

  function openChatMenu(chatId, anchor) {
    const chat = state.chats.find((item) => item.id === chatId);
    if (!chat) return;
    state.menuChatId = chatId;
    el.chatMenu.dataset.chatId = chatId;
    el.chatMenu.innerHTML = [
      '<button type="button" data-action="rename">Rename</button>',
      '<div class="menu-rule"></div>',
      '<button type="button" data-action="delete" class="menu-danger">Delete</button>'
    ].join('');
    el.chatMenu.hidden = false;

    const rect = anchor.getBoundingClientRect();
    const width = 190;
    const height = 100;
    const left = Math.min(
      Math.max(8, rect.right - width + 18),
      window.innerWidth - width - 8
    );
    let top = rect.bottom + 5;
    if (top + height > window.innerHeight - 8) {
      top = rect.top - height - 5;
    }
    el.chatMenu.style.left = `${left}px`;
    el.chatMenu.style.top = `${Math.max(8, top)}px`;
  }

  function closeChatMenu() {
    el.chatMenu.hidden = true;
    state.menuChatId = null;
  }

  function showDialog(html) {
    el.dialogCard.innerHTML = html;
    el.dialogLayer.hidden = false;
    closeChatMenu();
  }

  function closeDialog() {
    el.dialogLayer.hidden = true;
    el.dialogCard.innerHTML = '';
  }

  function openRenameDialog(chat) {
    closeDrawer();
    showDialog([
      '<h3>Rename chat</h3>',
      '<p>Choose a new name for this conversation.</p>',
      '<input class="text-input" id="renameInput" type="text" maxlength="80" autocomplete="off">',
      '<div class="dialog-actions">',
      '<button type="button" class="button button-ghost" data-dialog-close>Cancel</button>',
      '<button type="button" class="button button-primary" id="renameApply">Rename</button>',
      '</div>'
    ].join(''));

    const input = $('renameInput');
    input.value = chat.title || '';
    window.setTimeout(() => {
      input.focus();
      input.select();
    }, 50);

    const apply = () => {
      const title = input.value.replace(/\s+/g, ' ').trim();
      if (!title) {
        showToast('Enter a chat name.');
        input.focus();
        return;
      }
      chat.title = title.length <= 80 ? title : `${title.slice(0, 79)}…`;
      chat.updated_at = nowIso();
      persistChats();
      closeDialog();
      renderAll();
      showToast('Chat renamed.');
    };

    $('renameApply').addEventListener('click', apply);
    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        event.preventDefault();
        apply();
      }
    });
  }

  function openDeleteDialog(chat) {
    closeDrawer();
    showDialog([
      '<h3>Delete chat?</h3>',
      `<p>This will permanently remove <b></b> and its messages from this device.</p>`.replace(
        '<b></b>', '<b class="dialog-chat-name"></b>'),
      '<div class="dialog-actions">',
      '<button type="button" class="button button-ghost" data-dialog-close>Cancel</button>',
      '<button type="button" class="button button-danger" id="deleteApply">Delete</button>',
      '</div>'
    ].join(''));
    el.dialogCard.querySelector('.dialog-chat-name').textContent = chat.title || 'this chat';

    $('deleteApply').addEventListener('click', () => {
      state.chats = state.chats.filter((item) => item.id !== chat.id);
      persistChats();
      const wasCurrent = state.currentChat && state.currentChat.id === chat.id;
      if (wasCurrent) {
        const next = mostRecentChat();
        if (next) {
          state.currentChat = next;
          state.pendingReplyFor = null;
        } else {
          state.currentChat = null;
          newDraft(false);
        }
      }
      closeDialog();
      renderAll();
      persistUi();
      showToast('Chat deleted.');
    });
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function normalizeText(value) {
    return String(value || '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase();
  }

  function resolveAndroidMode(text, selected) {
    const lower = normalizeText(text);
    if (/^(hola|hello|hi|hey|gracias|thanks|ok|listo)\b/.test(lower)) return 'Default';
    if (selected && selected !== 'Default') return selected;
    if (/agent swapping|swap agents|multiagente|multi-agent|swarm|varios agentes|orquesta|delegar/.test(lower)) {
      return 'Agent Swapping';
    }
    if (/programa|programar|codigo|code|script|python|javascript|html|css|api|flask|vscode|terminal|test|bug|app|web|landing/.test(lower)) {
      return 'Programmer';
    }
    if (/investiga|research|fuentes|sources|paper|estudio|analisis profundo|benchmark|comparativa|noticias/.test(lower)) {
      return 'Deep Research';
    }
    return 'Default';
  }

  const ARTIFACT_TYPES = [
    { kind: 'pptx', ext: 'pptx', label: 'PowerPoint', badge: 'PPT', words: ['powerpoint', 'power point', 'pptx', 'ppt', 'presentacion', 'slides', 'diapositivas'] },
    { kind: 'xlsx', ext: 'xlsx', label: 'Excel', badge: 'XLS', words: ['excel', 'xlsx', 'xls', 'hoja de calculo', 'spreadsheet'] },
    { kind: 'docx', ext: 'docx', label: 'Word', badge: 'DOC', words: ['word', 'docx', 'documento de word'] },
    { kind: 'pdf', ext: 'pdf', label: 'PDF', badge: 'PDF', words: ['pdf'] },
    { kind: 'csv', ext: 'csv', label: 'CSV', badge: 'CSV', words: ['csv'] },
    { kind: 'html', ext: 'html', label: 'HTML', badge: 'HTML', words: ['html', 'pagina web', 'landing', 'web page'] },
    { kind: 'md', ext: 'md', label: 'Markdown', badge: 'MD', words: ['markdown', 'md'] },
    { kind: 'py', ext: 'py', label: 'Python', badge: 'PY', words: ['python'] },
    { kind: 'js', ext: 'js', label: 'JavaScript', badge: 'JS', words: ['javascript', 'typescript', 'node'] }
  ];

  function artifactTitle(text, type) {
    let value = String(text || '').replace(/\s+/g, ' ').trim();
    type.words.forEach((word) => {
      value = value.replace(new RegExp(`(^|\\W)${word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(\\W|$)`, 'gi'), ' ');
    });
    value = value.replace(/\b(crea|crear|creame|genera|generar|haz|hazme|elabora|prepara|exporta|construye|disena|programa|programar|make|create|generate|build|write)\b/gi, ' ');
    value = value.replace(/\b(un|una|uno|el|la|los|las|de|del|sobre|acerca de|for|about|on|the|a|an|que|con)\b/gi, ' ');
    value = value.replace(/\b(en|para|with|from|por|of)\s*$/i, ' ');
    value = value.replace(/\b\d+\s*(diapositivas?|slides?|paginas?|hojas?)\b/gi, ' ');
    value = value.replace(/\s+/g, ' ').replace(/^[\s.,:;_-]+|[\s.,:;_-]+$/g, '');
    if (!value) value = 'Documento Orunex';
    if (value.length > 72) value = `${value.slice(0, 69).trim()}...`;
    return value.charAt(0).toUpperCase() + value.slice(1);
  }

  function artifactLines(title) {
    return [
      'Resumen ejecutivo',
      `Este documento presenta una vision estructurada de ${title}.`,
      'El contenido esta organizado para revisar, compartir y ejecutar.',
      '',
      'Contexto',
      `El tema central es ${title}.`,
      'Antes de decidir conviene validar alcance, responsables y recursos.',
      '',
      'Puntos clave',
      '- Definir que significa exito.',
      '- Separar hechos, supuestos y decisiones pendientes.',
      '- Documentar responsables, fechas y criterios de aceptacion.',
      '- Revisar el resultado con una fuente independiente.',
      '',
      'Plan de accion',
      '1. Confirmar el objetivo y el publico destinatario.',
      '2. Reunir informacion y fuentes necesarias.',
      '3. Preparar una primera version del entregable.',
      '4. Validar, corregir y registrar la version final.',
      '',
      'Conclusion',
      `${title} queda preparado como un punto de partida concreto.`
    ].join('\n');
  }

  function artifactContent(kind, title) {
    if (kind === 'csv' || kind === 'xlsx') {
      return [
        'Elemento,Detalle,Cantidad,Valor',
        `Objetivo,Definir el alcance de ${title},1,0`,
        'Contexto,Reunir informacion y fuentes relevantes,3,0',
        'Analisis,Comparar alternativas y riesgos,4,0',
        'Ejecucion,Preparar el entregable principal,5,0',
        'Validacion,Revisar resultados con criterios de aceptacion,2,0',
        'Seguimiento,Registrar avances y proximos pasos,2,0'
      ].join('\n');
    }
    if (kind === 'pptx') {
      return [
        `Diapositiva 1: ${title}`,
        `Diapositiva 2: Contexto - ${title}`,
        'Diapositiva 3: Puntos clave - exito, supuestos y decisiones',
        'Diapositiva 4: Plan de accion - responsables, fechas y validacion',
        'Diapositiva 5: Siguiente paso - revisar y ejecutar'
      ].join('\n');
    }
    if (kind === 'py') {
      const lower = normalizeText(title);
      if (lower.includes('calculadora') || lower.includes('calculator')) {
        return [
          '"""Calculator starter generated by Orunex mobile."""',
          '',
          'def add(a, b):',
          '    return a + b',
          '',
          'def subtract(a, b):',
          '    return a - b',
          '',
          'def multiply(a, b):',
          '    return a * b',
          '',
          'def divide(a, b):',
          '    if b == 0:',
          '        raise ValueError("Cannot divide by zero")',
          '    return a / b',
          '',
          'if __name__ == "__main__":',
          '    print("2 + 3 =", add(2, 3))',
          '    print("10 / 2 =", divide(10, 2))'
        ].join('\n');
      }
      if (lower.includes('flask') || lower.includes('api')) {
        return [
          '"""Flask API starter generated by Orunex mobile."""',
          '',
          'from flask import Flask, jsonify',
          '',
          'app = Flask(__name__)',
          '',
          '@app.get("/health")',
          'def health():',
          '    return jsonify({"ok": True, "service": "orunex-api"})',
          '',
          '@app.get("/")',
          'def index():',
          '    return jsonify({"message": "Orunex API is running"})',
          '',
          'if __name__ == "__main__":',
          '    app.run(debug=True)'
        ].join('\n');
      }
      return [
        `"""Starter generated by Orunex for: ${title}."""`,
        '',
        'def describe():',
        `    return "Orunex project: ${title.replace(/"/g, "'")}"`,
        '',
        'def main():',
        '    print(describe())',
        '',
        'if __name__ == "__main__":',
        '    main()'
      ].join('\n');
    }
    if (kind === 'js') {
      return [
        '"use strict";',
        '',
        `// Starter generated by Orunex for: ${title}`,
        'function describe() {',
        `  return "Orunex project: ${title.replace(/"/g, "'")}";`,
        '}',
        '',
        'function add(a, b) {',
        '  return a + b;',
        '}',
        '',
        'console.log(describe());',
        'console.log("2 + 3 =", add(2, 3));'
      ].join('\n');
    }
    if (kind === 'html') {
      const safeTitle = escapeHtml(title);
      return `<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${safeTitle}</title>
  <style>
    body { margin: 0; background: #f4f8ff; color: #14213d; font-family: system-ui, sans-serif; }
    main { max-width: 860px; margin: 40px auto; padding: 40px; background: #fff; border: 1px solid #dfe9f7; border-radius: 20px; }
    h1 { font-size: 36px; line-height: 1.1; }
    h2 { color: #1e66f5; margin-top: 28px; }
    p, li { line-height: 1.6; }
  </style>
</head>
<body><main>
  <h1>${safeTitle}</h1>
  <p>Documento generado por Orunex en Android.</p>
  <h2>Contexto</h2><p>${safeTitle} es el tema central de esta pagina.</p>
  <h2>Puntos clave</h2>
  <ul><li>Definir el objetivo.</li><li>Reunir fuentes.</li><li>Validar el resultado.</li></ul>
  <h2>Plan de accion</h2>
  <ol><li>Confirmar alcance.</li><li>Preparar una version.</li><li>Revisar y publicar.</li></ol>
  <h2>Conclusion</h2><p>${safeTitle} queda listo como punto de partida.</p>
</main></body></html>`;
    }
    return artifactLines(title);
  }

  function slugify(value) {
    return normalizeText(value)
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/^_+|_+$/g, '')
      .slice(0, 48) || 'orunex_artifact';
  }

  function detectArtifactRequest(text) {
    const lower = normalizeText(text);
    if (/^(como|how|que es|what is)\b/.test(lower)) return null;
    const type = ARTIFACT_TYPES.find((item) => item.words.some((word) => {
      const pattern = new RegExp(`(^|\\W)${word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(\\W|$)`);
      return pattern.test(lower);
    }));
    const hasProgramming = /programa|programar|codigo|script|api|flask|calculadora|calculator/.test(lower);
    const verbs = /crea|crear|genera|generar|haz|hazme|elabora|prepara|exporta|construye|disena|programa|programar|make|create|generate|build|write|necesito|quiero|i need|i want/.test(lower);
    if (!type && !hasProgramming) return null;
    if (!verbs) return null;
    const actual = type || (lower.includes('javascript') || lower.includes('node')
      ? ARTIFACT_TYPES.find((item) => item.kind === 'js')
      : ARTIFACT_TYPES.find((item) => item.kind === 'py'));
    if (!actual) return null;
    const title = artifactTitle(text, actual);
    const date = new Date().toISOString().slice(0, 10).replace(/-/g, '');
    const filename = `${slugify(title)}_${date}.${actual.ext}`;
    const mime = {
      pdf: 'application/pdf',
      csv: 'text/csv',
      html: 'text/html',
      md: 'text/markdown',
      txt: 'text/plain',
      py: 'text/x-python',
      js: 'text/javascript'
    }[actual.kind] || 'application/octet-stream';
    return {
      kind: actual.kind,
      ext: actual.ext,
      badge: actual.badge,
      label: actual.label,
      title,
      filename,
      content: artifactContent(actual.kind, title),
      mime,
      downloadable: ['pdf', 'csv', 'html', 'md', 'txt', 'py', 'js'].includes(actual.kind)
    };
  }

  function pdfEscape(value) {
    return String(value || '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/\\/g, '\\\\')
      .replace(/\(/g, '\\(')
      .replace(/\)/g, '\\)')
      .replace(/[^\x20-\x7e]/g, ' ');
  }

  function buildPdfText(artifact) {
    const lines = [artifact.title].concat(String(artifact.content || '').split('\n')).slice(0, 70);
    const commands = ['BT', '/F1 18 Tf', '50 790 Td', `(${pdfEscape(lines[0])}) Tj`, '/F1 10 Tf', '0 -26 Td'];
    lines.slice(1).forEach((line) => {
      if (!line.trim()) {
        commands.push('0 -9 Td');
      } else {
        commands.push(`(${pdfEscape(line.slice(0, 92))}) Tj`, '0 -15 Td');
      }
    });
    commands.push('ET');
    const stream = commands.join('\n');
    const objects = [
      '<< /Type /Catalog /Pages 2 0 R >>',
      '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
      '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>',
      `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`,
      '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'
    ];
    let pdf = '%PDF-1.4\n';
    const offsets = [0];
    objects.forEach((object, index) => {
      offsets.push(pdf.length);
      pdf += `${index + 1} 0 obj\n${object}\nendobj\n`;
    });
    const xref = pdf.length;
    pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
    for (let index = 1; index <= objects.length; index += 1) {
      pdf += `${String(offsets[index]).padStart(10, '0')} 00000 n \n`;
    }
    pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`;
    return pdf;
  }

  function base64Utf8(value) {
    const bytes = new TextEncoder().encode(String(value || ''));
    let binary = '';
    const chunkSize = 0x8000;
    for (let index = 0; index < bytes.length; index += chunkSize) {
      binary += String.fromCharCode.apply(null, bytes.subarray(index, index + chunkSize));
    }
    return btoa(binary);
  }

  function downloadArtifact(artifact) {
    let payload = artifact.content;
    let filename = artifact.filename;
    let mime = artifact.mime;
    if (artifact.kind === 'pdf') {
      payload = buildPdfText(artifact);
      mime = 'application/pdf';
    }
    if (['xlsx', 'pptx', 'docx'].includes(artifact.kind)) {
      payload = `${artifact.title}\n\n${artifact.content}\n\nNota: el binario Office completo se exporta desde la app de escritorio.`;
      filename = filename.replace(/\.[^.]+$/, '.txt');
      mime = 'text/plain';
    }
    const nativeBridge = window.OrunexNative;
    if (nativeBridge && typeof nativeBridge.saveArtifact === 'function') {
      try {
        nativeBridge.saveArtifact(filename, mime, base64Utf8(payload));
        showToast(`Saved ${filename} to Downloads/Orunex`);
        return;
      } catch (error) {
        console.warn('Native artifact save failed:', error);
      }
    }
    try {
      const blob = new Blob([payload], { type: mime });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.setTimeout(() => URL.revokeObjectURL(url), 1500);
      showToast(`Downloaded ${filename}`);
    } catch (error) {
      showToast('Could not download the artifact');
    }
  }

  function openArtifact(artifact) {
    const office = ['xlsx', 'pptx', 'docx'].includes(artifact.kind);
    showDialog([
      `<h3>${escapeHtml(artifact.title)}</h3>`,
      `<p>${escapeHtml(artifact.label)} · ${escapeHtml(artifact.filename)}</p>`,
      `<pre class="artifact-preview">${escapeHtml(String(artifact.content || '').slice(0, 5000))}</pre>`,
      office ? '<p class="artifact-note">Vista previa en Android. El archivo Office completo se exporta desde Orunex Desktop.</p>' : '',
      '<div class="dialog-actions">',
      '<button type="button" class="button button-ghost" data-dialog-close>Close</button>',
      `<button type="button" class="button button-primary" id="artifactDownload">${office ? 'Download outline' : 'Download'}</button>`,
      '</div>'
    ].join(''));
    const download = document.getElementById('artifactDownload');
    if (download) {
      download.addEventListener('click', () => downloadArtifact(artifact));
    }
  }

  function buildArtifactCard(artifact) {
    const card = document.createElement('button');
    card.type = 'button';
    card.className = 'artifact-card';
    card.addEventListener('click', () => openArtifact(artifact));
    const icon = document.createElement('span');
    icon.className = `artifact-icon artifact-${artifact.kind}`;
    icon.textContent = artifact.badge || 'FILE';
    const copy = document.createElement('span');
    copy.className = 'artifact-copy';
    const name = document.createElement('strong');
    name.textContent = artifact.filename;
    const meta = document.createElement('span');
    meta.textContent = `${artifact.label} · ${artifact.title}`;
    copy.appendChild(name);
    copy.appendChild(meta);
    const action = document.createElement('span');
    action.className = 'artifact-action';
    action.textContent = 'Open';
    card.appendChild(icon);
    card.appendChild(copy);
    card.appendChild(action);
    return card;
  }

  function generateReply(text, mode, artifact) {
    const normalized = String(text || '').toLowerCase();
    if (artifact) {
      return [
        `Listo. Creé ${artifact.filename} con Artifact Studio.`,
        `Tipo: ${artifact.label} · Tema: ${artifact.title}`,
        'Puedes abrirlo desde la tarjeta de abajo. En Android la vista previa y la descarga estan disponibles; el control de VS Code y la terminal son exclusivos del escritorio.'
      ].join('\n\n');
    }
    if (mode === 'Programmer') {
      return [
        'Programmer mode listo. En escritorio abro VS Code, genero el proyecto, ejecuto pruebas y uso la terminal integrada.',
        'En Android puedo preparar el scaffold y las tarjetas de archivos; la conexion directa con la terminal es desktop-only.'
      ].join('\n\n');
    }
    if (mode === 'Deep Research') {
      return [
        'Deep Research mode listo. Organizaria la investigacion en fuentes, hallazgos, contraargumentos y proximos pasos.',
        'Dime el tema y preparo una sintesis estructurada con supuestos separados de hechos.'
      ].join('\n\n');
    }
    if (mode === 'Agent Swapping') {
      return [
        'Agent Swapping mode listo. Dividiria el trabajo en especialistas, compararia sus aportes y fusionaria el mejor resultado.',
        'Envia la mision y preparo el plan de orquestacion.'
      ].join('\n\n');
    }
    if (/^(hi|hello|hey|hola)\b/.test(normalized)) {
      return "Hello, I'm Orunex. Central operating core. How can I help you right now?";
    }
    if (normalized.includes('what can you do') || normalized.includes('capabilities') || normalized.includes('help me')) {
      return [
        'I can help you plan tasks, summarize documents, automate workflows, check system status and keep your conversations organized.',
        'This Android build mirrors the Orunex desktop interface and stores every conversation locally on your device.'
      ].join('\n\n');
    }
    if (normalized.includes('plan') || normalized.includes('task')) {
      return [
        'Here is a clean way to start:',
        '1. Define the outcome you want.\n2. List the constraints and available tools.\n3. Split the work into small verifiable steps.\n4. Review the result and refine it.',
        'Tell me the goal and I will turn it into a concrete plan.'
      ].join('\n\n');
    }
    if (normalized.includes('summar')) {
      return 'Attach a document with the Attach button and I will extract the key points. In this mobile build, the summary stays on your device and the conversation is saved automatically.';
    }
    if (normalized.includes('status') || normalized.includes('cpu') || normalized.includes('memory')) {
      return 'The Orunex mobile interface is running normally. Your chats are stored locally, and the animated composer pauses when the app is in the background. The desktop bridge is not connected in this preview.';
    }
    return [
      `I'm Orunex, your mobile operating core. I received: “${String(text).trim()}”.`,
      'This Android interface is ready and your conversation is stored locally on this device. Connect the desktop bridge when you want to run full tasks.'
    ].join('\n\n');
  }

  function sendMessage() {
    const text = el.composerInput.value.trim();
    if (!text) return;

    const chat = ensureCurrentChat();
    if (chat.isDraft) {
      chat.isDraft = false;
      if (!state.chats.some((item) => item.id === chat.id)) {
        state.chats.push(chat);
      }
    }

    chat.messages = Array.isArray(chat.messages) ? chat.messages : [];
    const time = nowIso();
    chat.messages.push({ role: 'user', text, time });
    chat.updated_at = time;
    if (!chat.title || chat.title === 'New chat') {
      chat.title = makeTitle(text);
    }

    persistChats();
    el.composerInput.value = '';
    state.pendingReplyFor = chat.id;
    renderAll();
    scrollToBottom();

    const chatId = chat.id;
    const selectedMode = state.settings.mode || 'Default';
    const resolvedMode = resolveAndroidMode(text, selectedMode);
    const artifact = detectArtifactRequest(text);
    const delay = 700 + Math.min(1100, text.length * 14);
    window.setTimeout(() => completeReply(chatId, text, selectedMode, resolvedMode, artifact), delay);
    persistUi();
  }

  function completeReply(chatId, userText, selectedMode, resolvedMode, artifact) {
    const chat = state.chats.find((item) => item.id === chatId);
    if (!chat) {
      if (state.pendingReplyFor === chatId) state.pendingReplyFor = null;
      renderAll();
      return;
    }

    const time = nowIso();
    const autoMode = resolvedMode && resolvedMode !== 'Default'
      && (!selectedMode || selectedMode === 'Default');
    let reply = generateReply(userText, resolvedMode || 'Default', artifact);
    if (autoMode) reply = `Auto mode: ${resolvedMode}.\n\n${reply}`;
    chat.messages = Array.isArray(chat.messages) ? chat.messages : [];
    chat.messages.push({
      role: 'assistant',
      tag: 'Cerebro',
      mode: resolvedMode || 'Default',
      text: reply,
      artifacts: artifact ? [artifact] : [],
      time
    });
    chat.updated_at = time;
    if (state.pendingReplyFor === chatId) state.pendingReplyFor = null;
    persistChats();

    if (state.currentChat && state.currentChat.id === chatId) {
      renderAll();
      scrollToBottom();
    } else {
      renderChatList();
    }
    persistUi();
  }

  function addSystemMessage(text) {
    const chat = ensureCurrentChat();
    chat.messages = Array.isArray(chat.messages) ? chat.messages : [];
    chat.messages.push({ role: 'system', text, time: nowIso() });
    chat.updated_at = nowIso();
    if (chat.isDraft) {
      chat.isDraft = false;
      if (!state.chats.some((item) => item.id === chat.id)) {
        state.chats.push(chat);
      }
    }
    persistChats();
    renderAll();
    scrollToBottom();
  }

  function copyText(text) {
    if (!text) return;
    const nativeCopied = nativeCall('copyText', text);
    if (nativeCopied !== null) return;
    try {
      const helper = document.createElement('textarea');
      helper.value = text;
      helper.setAttribute('readonly', '');
      helper.style.position = 'fixed';
      helper.style.opacity = '0';
      document.body.appendChild(helper);
      helper.select();
      const copied = document.execCommand('copy');
      document.body.removeChild(helper);
      showToast(copied ? 'Copied to clipboard' : 'Could not copy');
    } catch (error) {
      showToast('Could not copy');
    }
  }

  function showToast(message) {
    window.clearTimeout(state.toastTimer);
    el.toast.textContent = message;
    el.toast.classList.add('is-visible');
    state.toastTimer = window.setTimeout(() => {
      el.toast.classList.remove('is-visible');
    }, 2200);
  }

  function showFeedback(target, message) {
    const key = target.id;
    window.clearTimeout(state.feedbackTimers[key]);
    target.textContent = message;
    state.feedbackTimers[key] = window.setTimeout(() => {
      if (target.textContent === message) target.textContent = '';
    }, 3500);
  }

  function syncSettingsUi() {
    const settings = state.settings;
    el.displayName.value = settings.displayName || 'User';
    el.scaleRange.value = String(settings.scale || 100);
    el.autoHeal.checked = !!settings.autoHeal;
    el.saveMemory.checked = !!settings.saveMemory;
    el.screenGlow.checked = !!settings.screenGlow;
    el.retriesRange.value = String(settings.retries || 3);
    el.contextRange.value = String(settings.context || 16384);
    if (el.modeSelect) el.modeSelect.value = settings.mode || 'Default';
    updateScaleLabel();
    updateRetriesLabel();
    updateContextLabel();
    nativeCall('setTextZoom', Number(settings.scale) || 100);
  }

  function updateScaleLabel() {
    el.scaleLabel.textContent = `Interface scale: ${el.scaleRange.value}%`;
  }

  function updateRetriesLabel() {
    el.retriesLabel.textContent = `Maximum retries: ${el.retriesRange.value}`;
  }

  function updateContextLabel() {
    el.contextLabel.textContent = `Context window: ${Number(el.contextRange.value).toLocaleString('en-US')} tokens`;
  }

  function applySettings() {
    state.settings.displayName = el.displayName.value.replace(/\s+/g, ' ').trim() || 'User';
    state.settings.scale = Number(el.scaleRange.value) || 100;
    state.settings.autoHeal = el.autoHeal.checked;
    state.settings.saveMemory = el.saveMemory.checked;
    state.settings.screenGlow = el.screenGlow.checked;
    state.settings.retries = Number(el.retriesRange.value) || 3;
    state.settings.context = Number(el.contextRange.value) || 16384;
    persistSettings();
    nativeCall('setTextZoom', state.settings.scale);
    renderChat();
    showFeedback(el.settingsFeedback, 'Changes saved.');
    showToast('Settings saved.');
  }

  function syncSimplexUi() {
    const simplex = state.settings.simplex;
    const paired = !!simplex.paired;
    const contact = simplex.contact || 'Arturo_1';
    const link = String(simplex.link || '');

    el.simplexStatus.classList.toggle('is-offline', !paired);
    el.simplexStatus.innerHTML = `<i></i>${paired ? 'Paired' : 'Offline'}`;
    el.pairButton.textContent = paired ? 'Generate pairing link' : 'Start & pair';
    el.disconnectButton.hidden = !paired;
    el.disconnectButton.disabled = !paired;
    el.copyLinkButton.disabled = !link;
    el.simplexDetail.textContent = paired
      ? `Linked to ${contact}. Remote commands and notifications are active.`
      : 'Bridge disconnected. Start a new pairing to control Orunex remotely.';

    el.simplexLinkBox.textContent = link || 'No pairing link yet.';
    el.prefNotify.checked = !!simplex.notify;
    el.prefCommands.checked = !!simplex.commands;
    el.prefScreenshot.checked = !!simplex.screenshot;
    el.prefRemoteScreenshot.checked = !!simplex.remoteScreenshot;

    if (paired && link) {
      el.qrCard.classList.add('has-code');
      drawQrPreview(link);
    } else {
      el.qrCard.classList.remove('has-code');
    }
    updateDrawerStatus();
  }

  function randomToken(length) {
    const alphabet = 'abcdefghijklmnopqrstuvwxyz0123456789';
    const bytes = new Uint8Array(length);
    if (window.crypto && window.crypto.getRandomValues) {
      window.crypto.getRandomValues(bytes);
    } else {
      for (let i = 0; i < length; i += 1) {
        bytes[i] = Math.floor(Math.random() * 256);
      }
    }
    return Array.from(bytes, (byte) => alphabet[byte % alphabet.length]).join('');
  }

  function drawQrPreview(value) {
    const canvas = el.qrCanvas;
    if (!canvas || !canvas.getContext) return;
    const context = canvas.getContext('2d');
    if (!context) return;

    const size = canvas.width;
    const modules = 29;
    const quiet = 2;
    const cell = size / (modules + quiet * 2);
    let seed = 2166136261;
    for (let index = 0; index < value.length; index += 1) {
      seed ^= value.charCodeAt(index);
      seed = Math.imul(seed, 16777619) >>> 0;
    }
    const random = () => {
      seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
      return seed / 4294967296;
    };

    context.fillStyle = '#FFFFFF';
    context.fillRect(0, 0, size, size);
    context.fillStyle = '#131A56';

    const isFinder = (row, column) => {
      const topLeft = row < 7 && column < 7;
      const topRight = row < 7 && column >= modules - 7;
      const bottomLeft = row >= modules - 7 && column < 7;
      return topLeft || topRight || bottomLeft;
    };

    for (let row = 0; row < modules; row += 1) {
      for (let column = 0; column < modules; column += 1) {
        if (isFinder(row, column)) continue;
        if (random() > 0.55) {
          context.fillRect(
            Math.round((column + quiet) * cell),
            Math.round((row + quiet) * cell),
            Math.ceil(cell),
            Math.ceil(cell)
          );
        }
      }
    }

    const drawFinder = (row, column) => {
      const x = (column + quiet) * cell;
      const y = (row + quiet) * cell;
      const unit = cell;
      context.fillStyle = '#131A56';
      context.fillRect(x, y, unit * 7, unit * 7);
      context.fillStyle = '#FFFFFF';
      context.fillRect(x + unit, y + unit, unit * 5, unit * 5);
      context.fillStyle = '#131A56';
      context.fillRect(x + unit * 2, y + unit * 2, unit * 3, unit * 3);
    };

    drawFinder(0, 0);
    drawFinder(0, modules - 7);
    drawFinder(modules - 7, 0);
  }

  function generatePairing() {
    const simplex = state.settings.simplex;
    simplex.paired = true;
    simplex.contact = simplex.contact || 'Arturo_1';
    simplex.link = `simplex://orunex/pair?token=${randomToken(24)}`;
    persistSettings();
    syncSimplexUi();
    showFeedback(el.simplexFeedback, 'Pairing preview generated.');
    showToast('Pairing link generated.');
  }

  function disconnectSimplex() {
    const simplex = state.settings.simplex;
    simplex.paired = false;
    simplex.link = '';
    persistSettings();
    syncSimplexUi();
    showFeedback(el.simplexFeedback, 'Bridge disconnected.');
    showToast('Bridge disconnected.');
  }

  function saveSimplexPreferences() {
    const simplex = state.settings.simplex;
    simplex.notify = el.prefNotify.checked;
    simplex.commands = el.prefCommands.checked;
    simplex.screenshot = el.prefScreenshot.checked;
    simplex.remoteScreenshot = el.prefRemoteScreenshot.checked;
    persistSettings();
    showFeedback(el.simplexPrefsFeedback, 'Preferences saved.');
    showToast('Preferences saved.');
  }

  function chooseFile(accept, purpose) {
    state.filePurpose = purpose;
    el.fileInput.accept = accept;
    el.fileInput.value = '';
    el.fileInput.click();
  }

  function boot() {
    const rawChats = Store.loadChats();
    const firstRun = rawChats === '' || rawChats === null || rawChats === undefined;
    if (firstRun) {
      state.chats = [clone(DEFAULT_CHAT)];
      persistChats();
    } else {
      const parsed = parseJson(rawChats, []);
      state.chats = Array.isArray(parsed) ? parsed.filter(
        (chat) => chat && typeof chat === 'object' && Array.isArray(chat.messages)
      ) : [];
    }

    state.settings = mergeSettings(parseJson(Store.loadSettings(), {}));
    const uiState = parseJson(Store.loadUi(), {});

    const restored = uiState && uiState.currentChatId
      ? state.chats.find((chat) => chat.id === uiState.currentChatId)
      : null;
    const initial = restored || mostRecentChat();

    if (initial) {
      state.currentChat = initial;
    } else {
      state.currentChat = {
        id: uid(),
        title: 'New chat',
        created_at: nowIso(),
        updated_at: nowIso(),
        messages: [],
        isDraft: true
      };
    }

    state.view = 'chat';
    bindEvents();
    syncSettingsUi();
    syncSimplexUi();
    applyView();
    renderAll();
    scrollToBottom();

    window.setTimeout(() => {
      if (el.splash) el.splash.classList.add('is-hidden');
    }, 900);
    window.setTimeout(() => {
      if (el.splash && el.splash.parentNode) el.splash.parentNode.removeChild(el.splash);
      el.splash = null;
    }, 1600);
  }

  function bindEvents() {
    el.openDrawer.addEventListener('click', openDrawer);
    el.closeDrawer.addEventListener('click', closeDrawer);
    el.drawerScrim.addEventListener('click', closeDrawer);

    el.newChatButton.addEventListener('click', () => {
      if (state.currentChat && state.currentChat.isDraft && state.currentChat.messages.length === 0) {
        closeDrawer();
        el.composerInput.focus();
        return;
      }
      newDraft(true);
    });

    document.querySelectorAll('.nav-button[data-view]').forEach((button) => {
      button.addEventListener('click', () => setView(button.dataset.view));
    });

    el.drawerStatus.addEventListener('click', () => setView('simplex'));

    el.sendButton.addEventListener('click', sendMessage);
    if (el.modeSelect) {
      el.modeSelect.addEventListener('change', () => {
        state.settings.mode = el.modeSelect.value || 'Default';
        persistSettings();
        showToast(`${state.settings.mode} mode ready`);
      });
    }
    el.composerInput.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.isComposing) {
        event.preventDefault();
        sendMessage();
      }
    });
    el.composerInput.addEventListener('focus', () => {
      window.setTimeout(scrollToBottom, 260);
    });

    el.attachButton.addEventListener('click', () => {
      chooseFile('image/*,application/pdf,.txt,.json', 'attach');
    });

    el.fileInput.addEventListener('change', () => {
      const file = el.fileInput.files && el.fileInput.files[0];
      if (!file) return;
      if (state.filePurpose === 'knowledge') {
        showToast(`Queued ${file.name} for the local knowledge base.`);
        showFeedback(el.settingsFeedback, `Queued ${file.name}.`);
      } else {
        addSystemMessage(`Attached: ${file.name}`);
        showToast(`Attached ${file.name}`);
      }
      el.fileInput.value = '';
    });

    el.suggestionGrid.addEventListener('click', (event) => {
      const button = event.target.closest('.suggestion');
      if (!button) return;
      el.composerInput.value = button.dataset.prompt || '';
      el.composerInput.focus();
    });

    el.chatMenu.addEventListener('click', (event) => {
      const action = event.target.closest('button[data-action]');
      if (!action) return;
      event.stopPropagation();
      const chat = state.chats.find((item) => item.id === state.menuChatId);
      closeChatMenu();
      if (!chat) return;
      if (action.dataset.action === 'rename') {
        openRenameDialog(chat);
      } else if (action.dataset.action === 'delete') {
        openDeleteDialog(chat);
      }
    });

    document.addEventListener('click', (event) => {
      if (!el.chatMenu.hidden
          && !el.chatMenu.contains(event.target)
          && !event.target.closest('.chat-more')) {
        closeChatMenu();
      }
    });

    el.dialogLayer.addEventListener('click', (event) => {
      if (event.target === el.dialogLayer || event.target.closest('[data-dialog-close]')) {
        closeDialog();
      }
    });

    el.scaleRange.addEventListener('input', updateScaleLabel);
    el.retriesRange.addEventListener('input', updateRetriesLabel);
    el.contextRange.addEventListener('input', updateContextLabel);
    el.saveSettingsButton.addEventListener('click', applySettings);
    el.manageMemory.addEventListener('click', () => {
      const messages = state.chats.reduce(
        (total, chat) => total + (Array.isArray(chat.messages) ? chat.messages.length : 0), 0);
      showToast(`${state.chats.length} chats and ${messages} messages stored locally.`);
    });
    el.uploadJson.addEventListener('click', () => chooseFile('.json,application/json', 'knowledge'));
    el.uploadPdf.addEventListener('click', () => chooseFile('.pdf,application/pdf', 'knowledge'));
    el.openSimplexFromSettings.addEventListener('click', () => setView('simplex'));

    el.pairButton.addEventListener('click', generatePairing);
    el.disconnectButton.addEventListener('click', disconnectSimplex);
    el.saveSimplexPrefs.addEventListener('click', saveSimplexPreferences);
    el.copyLinkButton.addEventListener('click', () => {
      const link = state.settings.simplex.link;
      if (!link) {
        showFeedback(el.simplexFeedback, 'No pairing link yet.');
        return;
      }
      copyText(link);
      showFeedback(el.simplexFeedback, 'Link copied to the clipboard.');
    });

    document.addEventListener('keydown', (event) => {
      if (event.key !== 'Escape') return;
      if (!el.dialogLayer.hidden) {
        closeDialog();
      } else if (!el.chatMenu.hidden) {
        closeChatMenu();
      } else if (el.drawer.classList.contains('is-open')) {
        closeDrawer();
      }
    });

    window.addEventListener('resize', () => {
      window.setTimeout(scrollToBottom, 160);
    });
    window.addEventListener('orientationchange', () => {
      window.setTimeout(scrollToBottom, 240);
    });

    document.addEventListener('visibilitychange', () => {
      document.body.classList.toggle('is-paused', document.hidden);
    });

    let edgeTouchStart = null;
    el.app.addEventListener('touchstart', (event) => {
      const touch = event.touches && event.touches[0];
      if (!touch) return;
      if (!el.drawer.classList.contains('is-open') && touch.clientX <= 22) {
        edgeTouchStart = { x: touch.clientX, y: touch.clientY };
      } else {
        edgeTouchStart = null;
      }
    }, { passive: true });

    el.app.addEventListener('touchend', (event) => {
      if (!edgeTouchStart) return;
      const touch = event.changedTouches && event.changedTouches[0];
      if (!touch) return;
      const dx = touch.clientX - edgeTouchStart.x;
      const dy = Math.abs(touch.clientY - edgeTouchStart.y);
      if (dx > 52 && dy < 46) openDrawer();
      edgeTouchStart = null;
    }, { passive: true });

    window.OrunexHandleBack = () => {
      if (!el.dialogLayer.hidden) {
        closeDialog();
        return true;
      }
      if (!el.chatMenu.hidden) {
        closeChatMenu();
        return true;
      }
      if (el.drawer.classList.contains('is-open')) {
        closeDrawer();
        return true;
      }
      if (state.view !== 'chat') {
        setView('chat');
        return true;
      }
      return false;
    };
  }

  if (document.readyState === 'loading') {
    window.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
