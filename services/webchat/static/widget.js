/**
 * Webchat Widget - Canal Webchat Embebible
 * Implementado en Vanilla JS con Shadow DOM para aislamiento total de estilos.
 * No requiere React ni dependencias externas en el sitio del cliente.
 */
(function() {
    // Evitar instanciación duplicada si el script se incluye más de una vez
    if (window.__WEBCHAT_INITIALIZED__) return;
    window.__WEBCHAT_INITIALIZED__ = true;

    // 1. Obtener parámetros de configuración del script tag
    const currentScript = document.currentScript || document.getElementById('webchat-script') || document.querySelector('script[src*="widget.js"]');
    const orgId = currentScript ? parseInt(currentScript.getAttribute('data-org-id') || "1", 10) : 1;
    const apiUrl = (currentScript ? currentScript.getAttribute('data-api-url') : null) || window.location.origin;
    const themeColor = (currentScript ? currentScript.getAttribute('data-color') : null) || "#1e40af";
    const widgetTitle = (currentScript ? currentScript.getAttribute('data-title') : null) || "Atención al Cliente";

    // 2. Gestión de identidad del visitante (visitor_id persistente en localStorage)
    const STORAGE_KEY_VISITOR = "webchat_visitor_id";
    const STORAGE_KEY_HISTORY = `webchat_history_${orgId}`;

    function getOrCreateVisitorId() {
        let visitorId = localStorage.getItem(STORAGE_KEY_VISITOR);
        if (!visitorId) {
            visitorId = (typeof crypto !== "undefined" && crypto.randomUUID) 
                ? crypto.randomUUID() 
                : "vis_" + Math.random().toString(36).substring(2, 15) + "_" + Date.now().toString(36);
            localStorage.setItem(STORAGE_KEY_VISITOR, visitorId);
        }
        return visitorId;
    }

    const visitorId = getOrCreateVisitorId();

    // 3. Crear contenedor y Shadow DOM para aislar CSS
    const hostElement = document.createElement("div");
    hostElement.id = "webchat-widget-root";
    document.body.appendChild(hostElement);
    const shadow = hostElement.attachShadow({ mode: "open" });

    // 4. Estilos CSS encapsulados
    const styleElement = document.createElement("style");
    styleElement.textContent = `
        :host {
            --primary-color: ${themeColor};
            --primary-hover: #1e3a8a;
            --bg-color: #ffffff;
            --text-color: #1f2937;
            --bot-bubble-bg: #f3f4f6;
            --bot-bubble-text: #111827;
            --user-bubble-bg: ${themeColor};
            --user-bubble-text: #ffffff;
            --operator-bubble-bg: #e0e7ff;
            --operator-bubble-text: #1e1b4b;
            --border-color: #e5e7eb;
            --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            z-index: 2147483647;
            position: fixed;
            bottom: 20px;
            right: 20px;
            font-family: var(--font-family);
            line-height: 1.5;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        /* Botón disparador flotante */
        .chat-launcher {
            width: 60px;
            height: 60px;
            border-radius: 30px;
            background-color: var(--primary-color);
            color: #ffffff;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.2);
            transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1), background-color 0.2s;
            border: none;
            outline: none;
        }

        .chat-launcher:hover {
            transform: scale(1.05);
            background-color: var(--primary-hover);
        }

        .chat-launcher svg {
            width: 28px;
            height: 28px;
            fill: currentColor;
            transition: transform 0.2s;
        }

        /* Ventana de chat flotante */
        .chat-window {
            display: none;
            flex-direction: column;
            width: 380px;
            height: 560px;
            max-width: calc(100vw - 40px);
            max-height: calc(100vh - 100px);
            background-color: var(--bg-color);
            border-radius: 16px;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15);
            border: 1px solid var(--border-color);
            overflow: hidden;
            margin-bottom: 12px;
            animation: slideUp 0.25s ease-out forwards;
        }

        .chat-window.open {
            display: flex;
        }

        @keyframes slideUp {
            from { opacity: 0; transform: translateY(16px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Encabezado */
        .chat-header {
            background-color: var(--primary-color);
            color: #ffffff;
            padding: 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .header-info {
            display: flex;
            flex-direction: column;
        }

        .header-title {
            font-size: 16px;
            font-weight: 600;
        }

        .header-status {
            font-size: 12px;
            display: flex;
            align-items: center;
            gap: 6px;
            opacity: 0.9;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            background-color: #10b981;
            border-radius: 50%;
        }

        .status-dot.disconnected {
            background-color: #ef4444;
        }

        .close-btn {
            background: none;
            border: none;
            color: #ffffff;
            cursor: pointer;
            padding: 4px;
            border-radius: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
            opacity: 0.85;
            transition: opacity 0.15s;
        }

        .close-btn:hover {
            opacity: 1;
        }

        /* Área de mensajes */
        .messages-container {
            flex: 1;
            padding: 16px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 12px;
            background-color: #f9fafb;
        }

        .message-bubble {
            max-width: 82%;
            padding: 10px 14px;
            border-radius: 12px;
            font-size: 14px;
            word-break: break-word;
            line-height: 1.45;
        }

        .message-bubble.user {
            align-self: flex-end;
            background-color: var(--user-bubble-bg);
            color: var(--user-bubble-text);
            border-bottom-right-radius: 4px;
        }

        .message-bubble.bot {
            align-self: flex-start;
            background-color: var(--bot-bubble-bg);
            color: var(--bot-bubble-text);
            border-bottom-left-radius: 4px;
            border: 1px solid #e5e7eb;
        }

        .message-bubble.operator {
            align-self: flex-start;
            background-color: var(--operator-bubble-bg);
            color: var(--operator-bubble-text);
            border-bottom-left-radius: 4px;
            border: 1px solid #c7d2fe;
        }

        .operator-tag {
            font-size: 11px;
            font-weight: 600;
            color: #4338ca;
            margin-bottom: 2px;
        }

        /* Marcado enriquecido (Markdown neutro) */
        .message-bubble strong { font-weight: 700; }
        .message-bubble em { font-style: italic; }
        .message-bubble del { text-decoration: line-through; }
        .message-bubble code {
            font-family: monospace;
            background: rgba(0, 0, 0, 0.08);
            padding: 2px 4px;
            border-radius: 3px;
            font-size: 12px;
        }

        /* Menú interactivo nativo (Botones de opciones de Core) */
        .menu-container {
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-top: 6px;
        }

        .menu-title {
            font-weight: 600;
            font-size: 13px;
            margin-bottom: 2px;
        }

        .menu-btn {
            background-color: #ffffff;
            color: var(--primary-color);
            border: 1px solid var(--primary-color);
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            text-align: left;
            transition: all 0.15s ease;
        }

        .menu-btn:hover:not(:disabled) {
            background-color: var(--primary-color);
            color: #ffffff;
        }

        .menu-btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            background-color: #f3f4f6;
            border-color: #d1d5db;
            color: #6b7280;
        }

        /* Indicador de escribiendo */
        .typing-indicator {
            align-self: flex-start;
            display: none;
            align-items: center;
            gap: 4px;
            padding: 8px 12px;
            background-color: var(--bot-bubble-bg);
            border-radius: 12px;
            border: 1px solid #e5e7eb;
        }

        .typing-indicator.active {
            display: flex;
        }

        .typing-dot {
            width: 6px;
            height: 6px;
            background-color: #9ca3af;
            border-radius: 50%;
            animation: bounce 1.2s infinite;
        }

        .typing-dot:nth-child(2) { animation-delay: 0.2s; }
        .typing-dot:nth-child(3) { animation-delay: 0.4s; }

        @keyframes bounce {
            0%, 60%, 100% { transform: translateY(0); }
            30% { transform: translateY(-4px); }
        }

        /* Input y Envío */
        .chat-input-area {
            padding: 12px;
            background-color: #ffffff;
            border-top: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .chat-input {
            flex: 1;
            padding: 10px 14px;
            font-size: 14px;
            border: 1px solid var(--border-color);
            border-radius: 20px;
            outline: none;
            transition: border-color 0.15s;
            font-family: inherit;
        }

        .chat-input:focus {
            border-color: var(--primary-color);
        }

        .send-btn {
            background-color: var(--primary-color);
            color: #ffffff;
            border: none;
            width: 38px;
            height: 38px;
            border-radius: 19px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: background-color 0.15s, transform 0.1s;
        }

        .send-btn:hover {
            background-color: var(--primary-hover);
        }

        .send-btn:active {
            transform: scale(0.95);
        }

        .send-btn svg {
            width: 18px;
            height: 18px;
            fill: currentColor;
        }

        /* Mobile Responsive */
        @media (max-width: 480px) {
            :host {
                bottom: 0;
                right: 0;
                width: 100%;
            }
            .chat-launcher {
                position: fixed;
                bottom: 20px;
                right: 20px;
            }
            .chat-window {
                width: 100vw;
                height: 100vh;
                max-width: 100vw;
                max-height: 100vh;
                border-radius: 0;
                margin-bottom: 0;
            }
        }
    `;
    shadow.appendChild(styleElement);

    // 5. Estructura HTML del Widget
    const container = document.createElement("div");
    container.innerHTML = `
        <div class="chat-window" id="chatWindow">
            <div class="chat-header">
                <div class="header-info">
                    <span class="header-title">${widgetTitle}</span>
                    <span class="header-status">
                        <span class="status-dot" id="statusDot"></span>
                        <span id="statusText">Conectado</span>
                    </span>
                </div>
                <button class="close-btn" id="closeBtn" aria-label="Cerrar chat">
                    <svg viewBox="0 0 24 24" width="20" height="20">
                        <path fill="currentColor" d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                    </svg>
                </button>
            </div>

            <div class="messages-container" id="messagesContainer">
                <!-- Los mensajes se agregan dinámicamente -->
            </div>

            <div class="typing-indicator" id="typingIndicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>

            <form class="chat-input-area" id="chatForm">
                <input type="text" class="chat-input" id="messageInput" placeholder="Escribe un mensaje..." autocomplete="off" />
                <button type="submit" class="send-btn" id="sendBtn" aria-label="Enviar mensaje">
                    <svg viewBox="0 0 24 24">
                        <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
                    </svg>
                </button>
            </form>
        </div>

        <button class="chat-launcher" id="chatLauncher" aria-label="Abrir chat">
            <svg viewBox="0 0 24 24" id="launcherIcon">
                <path d="M20 2H4c-1.1 0-1.99.9-1.99 2L2 22l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zM6 9h12v2H6V9zm8 5H6v-2h8v2zm4-6H6V6h12v2z"/>
            </svg>
        </button>
    `;
    shadow.appendChild(container);

    // 6. Referencias a Elementos del DOM
    const chatWindow = shadow.getElementById("chatWindow");
    const chatLauncher = shadow.getElementById("chatLauncher");
    const closeBtn = shadow.getElementById("closeBtn");
    const messagesContainer = shadow.getElementById("messagesContainer");
    const chatForm = shadow.getElementById("chatForm");
    const messageInput = shadow.getElementById("messageInput");
    const statusDot = shadow.getElementById("statusDot");
    const statusText = shadow.getElementById("statusText");
    const typingIndicator = shadow.getElementById("typingIndicator");

    let isChatOpen = false;
    let socket = null;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 5;

    // 7. Funciones de Renderizado y Formato (Markdown Neutro y XSS Safe)
    function sanitizeAndFormatMarkdown(rawText) {
        if (!rawText) return "";
        // Sanitizar contra XSS convirtiendo a entidades HTML
        const div = document.createElement("div");
        div.textContent = rawText;
        let safe = div.innerHTML;

        // Marcado neutro según especificación §2.5 / §4.1.2:
        // **negrita**
        safe = safe.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
        // _cursiva_
        safe = safe.replace(/_(.*?)_/g, "<em>$1</em>");
        // ~tachado~
        safe = safe.replace(/~(.*?)~/g, "<del>$1</del>");
        // `código`
        safe = safe.replace(/`(.*?)`/g, "<code>$1</code>");
        // Saltos de línea
        safe = safe.replace(/\n/g, "<br/>");

        return safe;
    }

    // Guardar y recuperar historial local
    function saveMessageToLocalHistory(msg) {
        try {
            const history = JSON.parse(localStorage.getItem(STORAGE_KEY_HISTORY) || "[]");
            history.push(msg);
            // Conservar últimos 50 mensajes
            if (history.length > 50) history.shift();
            localStorage.setItem(STORAGE_KEY_HISTORY, JSON.stringify(history));
        } catch (e) {}
    }

    function loadLocalHistory() {
        try {
            const history = JSON.parse(localStorage.getItem(STORAGE_KEY_HISTORY) || "[]");
            history.forEach(item => {
                if (item.tipo === "user") appendUserMessage(item.texto, false);
                else if (item.tipo === "bot") appendBotMessage(item.texto, false);
                else if (item.tipo === "operator") appendOperatorMessage(item.texto, false);
                else if (item.tipo === "menu") appendMenuMessage(item, false);
            });
        } catch (e) {}
    }

    function appendUserMessage(text, save = true) {
        const bubble = document.createElement("div");
        bubble.className = "message-bubble user";
        bubble.innerHTML = sanitizeAndFormatMarkdown(text);
        messagesContainer.appendChild(bubble);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        if (save) saveMessageToLocalHistory({ tipo: "user", texto: text });
    }

    function appendBotMessage(text, save = true) {
        const bubble = document.createElement("div");
        bubble.className = "message-bubble bot";
        bubble.innerHTML = sanitizeAndFormatMarkdown(text);
        messagesContainer.appendChild(bubble);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        if (save) saveMessageToLocalHistory({ tipo: "bot", texto: text });
    }

    function appendOperatorMessage(text, save = true) {
        const bubble = document.createElement("div");
        bubble.className = "message-bubble operator";
        bubble.innerHTML = `<div class="operator-tag">Operador</div>` + sanitizeAndFormatMarkdown(text);
        messagesContainer.appendChild(bubble);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        if (save) saveMessageToLocalHistory({ tipo: "operator", texto: text });
    }

    // Renderizar menú nativo con botones (§2.4)
    function appendMenuMessage(menuData, save = true) {
        const bubble = document.createElement("div");
        bubble.className = "message-bubble bot";

        let html = "";
        if (menuData.encabezado) {
            html += `<div class="menu-title">${sanitizeAndFormatMarkdown(menuData.encabezado)}</div>`;
        }
        if (menuData.texto) {
            html += `<div>${sanitizeAndFormatMarkdown(menuData.texto)}</div>`;
        }

        const menuBox = document.createElement("div");
        menuBox.className = "menu-container";
        bubble.innerHTML = html;
        bubble.appendChild(menuBox);

        const opciones = menuData.opciones || [];
        opciones.forEach(opcion => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "menu-btn";
            btn.textContent = opcion.titulo;
            btn.onclick = () => {
                // Deshabilitar todos los botones de este menú tras la selección
                menuBox.querySelectorAll("button").forEach(b => b.disabled = true);
                // Enviar la opción elegida a Core
                enviarMensaje(opcion.id || opcion.titulo);
            };
            menuBox.appendChild(btn);
        });

        messagesContainer.appendChild(bubble);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        if (save) saveMessageToLocalHistory({ tipo: "menu", ...menuData });
    }

    // 8. Comunicación WebSocket (Canal de bajada en tiempo real)
    function connectWebSocket() {
        const wsProto = apiUrl.startsWith("https") ? "wss:" : "ws:";
        const host = apiUrl.replace(/^https?:\/\//, "");
        const wsUrl = `${wsProto}//${host}/ws/visitante/${visitorId}`;

        socket = new WebSocket(wsUrl);

        socket.onopen = () => {
            reconnectAttempts = 0;
            statusDot.className = "status-dot";
            statusText.textContent = "Conectado";
        };

        socket.onmessage = (event) => {
            hideTyping();
            try {
                const data = JSON.parse(event.data);
                if (data.tipo === "mensaje_bot") {
                    appendBotMessage(data.texto);
                } else if (data.tipo === "menu") {
                    appendMenuMessage(data);
                } else if (data.tipo === "mensaje_operador") {
                    appendOperatorMessage(data.texto);
                }
            } catch (e) {
                console.error("[Webchat] Error parseando evento WS:", e);
            }
        };

        socket.onclose = () => {
            statusDot.className = "status-dot disconnected";
            statusText.textContent = "Desconectado";
            // Reintento con backoff exponencial
            if (reconnectAttempts < maxReconnectAttempts) {
                const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000);
                reconnectAttempts++;
                setTimeout(connectWebSocket, delay);
            }
        };

        socket.onerror = () => {
            socket.close();
        };
    }

    function showTyping() {
        typingIndicator.classList.add("active");
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    function hideTyping() {
        typingIndicator.classList.remove("active");
    }

    // 9. Envío de Mensajes (REST POST /mensajes/)
    async function enviarMensaje(texto) {
        const mensajeLimpio = texto.trim();
        if (!mensajeLimpio) return;

        appendUserMessage(mensajeLimpio);
        showTyping();

        try {
            const res = await fetch(`${apiUrl}/mensajes/`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    organization_id: orgId,
                    visitor_id: visitorId,
                    texto: mensajeLimpio
                })
            });

            if (!res.ok) {
                hideTyping();
                appendBotMessage("Lo sentimos, no pudimos procesar tu mensaje. Intenta nuevamente.");
            }
        } catch (err) {
            hideTyping();
            appendBotMessage("Error de conexión con el servicio de chat.");
        }
    }

    // 10. Handshake inicial de Sesión (POST /sessions/)
    async function inicializarSesion() {
        try {
            const res = await fetch(`${apiUrl}/sessions/`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    organization_id: orgId,
                    visitor_id: visitorId
                })
            });
            if (res.ok) {
                const data = await res.json();
                // Si el servidor ya tenía historial en Core y el local está vacío, cargar el de Core
                const localHistory = JSON.parse(localStorage.getItem(STORAGE_KEY_HISTORY) || "[]");
                if (localHistory.length === 0 && data.historial && data.historial.length > 0) {
                    data.historial.forEach(m => {
                        if (m.origen === "visitante") appendUserMessage(m.texto, true);
                        else appendBotMessage(m.texto, true);
                    });
                }
            }
        } catch (e) {
            console.warn("[Webchat] Sesión inicializada en modo offline");
        }
    }

    // 11. Event Listeners y Toggle de UI
    chatLauncher.addEventListener("click", () => {
        isChatOpen = !isChatOpen;
        if (isChatOpen) {
            chatWindow.classList.add("open");
            chatLauncher.style.display = "none";
            messageInput.focus();
        } else {
            chatWindow.classList.remove("open");
            chatLauncher.style.display = "flex";
        }
    });

    closeBtn.addEventListener("click", () => {
        isChatOpen = false;
        chatWindow.classList.remove("open");
        chatLauncher.style.display = "flex";
    });

    chatForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const texto = messageInput.value;
        if (texto.trim()) {
            enviarMensaje(texto);
            messageInput.value = "";
        }
    });

    // 12. Arranque
    loadLocalHistory();
    inicializarSesion();
    connectWebSocket();
})();
