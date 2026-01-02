console.log("--- BACKGROUND.JS: VERSIÓN AUTO-REPARABLE ---");

const NATIVE_HOST_NAME = "com.examen.proctoring";
let nativePort = null;
let examTabId = null;
let isExamActive = false;
let isConnecting = false;
let examWindowId = null; 
let activeExamenId = null;

// --- CONEXIÓN NATIVA ---
function connectNative() {
  if (isConnecting) return; // Evitar doble intento
  isConnecting = true; 
  
  console.log("Intentando conectar con Agente Nativo...");
  try {
    nativePort = chrome.runtime.connectNative(NATIVE_HOST_NAME);
    
    nativePort.onMessage.addListener(onNativeMessage);
    
    // Si se desconecta solo (crash del python), manejarlo
    nativePort.onDisconnect.addListener(onNativeDisconnect);
    
    isConnecting = false; 
    sendMessageToContent({ type: "AGENT_STATUS", connected: true });
    console.log("Conexión exitosa.");
    
  } catch (error) {
    console.error("Error al conectar:", error);
    isConnecting = false; 
    sendMessageToContent({ type: "AGENT_STATUS", connected: false, error: error.message });
  }
}

function onNativeMessage(message) {
  // Reenviar todo a la pestaña activa
  sendMessageToContent(message); 
  
  // Seguridad: Si el agente grita PLAGIO y estamos en examen, actuamos
  if (message.type === 'PLAGIO_DETECTED' && isExamActive) {
    handlePlagio(`apertura de ${message.app}`);
  }
}

function onNativeDisconnect() {
  const error = chrome.runtime.lastError ? chrome.runtime.lastError.message : "Desconexión inesperada";
  console.warn("El Agente se desconectó:", error);
  
  nativePort = null;
  isConnecting = false; 
  
  sendMessageToContent({ type: "AGENT_STATUS", connected: false, error: "Agente desconectado" });
  
  if (isExamActive) {
    handlePlagio("desconexión crítica del agente de seguridad");
  }
}

function sendNativeMessage(msg) {
  if (nativePort) {
      try {
        nativePort.postMessage(msg);
      } catch (e) {
          console.error("Error enviando mensaje al nativo:", e);
          // Si falla el envío, forzamos desconexión para intentar reconectar luego
          onNativeDisconnect();
      }
  }
}

// --- LISTENER DE MENSAJES DESDE EL CONTENIDO ---
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  
  // 1. CARGA DE PÁGINA (AQUÍ ESTÁ EL ARREGLO)
  if (message.type === 'PAGE_LOADED') {
    examTabId = sender.tab.id;
    examWindowId = sender.tab.windowId; 
    activeExamenId = message.examen_id; 

    if (message.page === 'welcome') {
        isExamActive = false; // Seguridad: Apagamos monitoreo activo
        
        // --- LA SOLUCIÓN: REINICIO FORZADO ---
        // Si ya había un puerto abierto de una sesión anterior, lo matamos.
        // Esto "resetea" el Python para que no se quede con hilos colgados.
        if (nativePort) {
            console.log("Reiniciando agente para nueva sesión...");
            try {
                nativePort.disconnect(); // Esto cierra el .exe
            } catch(e) {}
            nativePort = null;
        }
        // Iniciamos uno fresco
        connectNative();
        // --------------------------------------
        
    } else if (message.page === 'exam') {
      isExamActive = true;
      // Si estamos en el examen, aseguramos conexión y arrancamos monitoreo
      if (!nativePort) connectNative();
      sendNativeMessage({ command: 'START_MONITORING' });
    }
    sendResponse({ status: "ok" });
  }
  
  // 2. REPORTE DE PLAGIO (Validado)
  else if (message.type === 'PLAGIO_DETECTED') {
      if (isExamActive) { 
          handlePlagio(message.reason);
      }
  }

  // 3. FIN DEL EXAMEN
  else if (message.type === 'EXAM_FINISHED') {
    isExamActive = false;
    activeExamenId = null;
    sendNativeMessage({ command: 'STOP_MONITORING' });
    chrome.storage.local.remove(['isFinishingExam', 'plagioFlag']); 
    sendResponse({status: 'ack'});
  }

  // 4. CHEQUEOS DE RUTINA
  else if (message.type === 'CHECK_ENVIRONMENT') {
    checkBrowserState(); 
    // Solo pedimos chequeo de apps si tenemos puerto
    if (nativePort) sendNativeMessage({ command: 'CHECK_APPS' });
    else {
        // Si no hay puerto (caso raro), intentamos reconectar suavemente
        connectNative();
    }
  }

  else if (message.type === 'PING') {
    sendResponse({ status: 'PONG' });
  }

  else if (message.type === 'CLOSE_ALL') {
    cleanBrowserState(); 
    sendNativeMessage({ command: 'CLOSE_APPS' }); 
  }
  return true; 
});

// --- MONITORES DE NAVEGADOR ---
chrome.tabs.onCreated.addListener(function(tab) {
    if (isExamActive) handlePlagio("apertura de nueva pestaña");
});

chrome.windows.onFocusChanged.addListener(function(windowId) {
    if (!isExamActive || !examWindowId) return;
    if (windowId !== examWindowId && windowId !== chrome.windows.WINDOW_ID_NONE) {
        handlePlagio("cambio de ventana no autorizado");
    }
});

// --- FUNCIONES AUXILIARES ---
function sendMessageToContent(message) {
  if (examTabId) {
    chrome.tabs.sendMessage(examTabId, message, () => {
      if (chrome.runtime.lastError) {} // Ignorar si la pestaña se cerró
    });
  }
}

async function checkBrowserState() {
    if (!examWindowId) return; 
    let isClean = true;
    let failReason = "";
    try {
        const currentWindow = await chrome.windows.get(examWindowId, { populate: true });
        if (currentWindow.incognito) { isClean = false; failReason = "Modo incógnito detectado"; }
        
        const otherTabs = currentWindow.tabs.filter(tab => tab.id !== examTabId && !tab.url.startsWith("chrome://"));
        if (otherTabs.length > 0) { isClean = false; failReason = `${otherTabs.length} pestañas extra`; }
        
        const allWindows = await chrome.windows.getAll();
        const otherWindows = allWindows.filter(w => w.id !== examWindowId && w.type === 'normal');
        if (otherWindows.length > 0) { isClean = false; failReason = "Otras ventanas abiertas"; }
    } catch (e) { console.log("Error checking browser:", e); }
    
    sendMessageToContent({ type: 'BROWSER_STATUS', isClean: isClean, message: failReason });
}

async function cleanBrowserState() {
    if (!examWindowId) return;
    const currentWindow = await chrome.windows.get(examWindowId, {populate: true});
    
    // Cerrar Tabs extra
    const tabsToClose = currentWindow.tabs
        .filter(tab => tab.id !== examTabId && !tab.url.startsWith("chrome://"))
        .map(t => t.id);
    if (tabsToClose.length > 0) await chrome.tabs.remove(tabsToClose);

    // Cerrar Ventanas extra
    const allWindows = await chrome.windows.getAll();
    const windowsToClose = allWindows
        .filter(w => w.id !== examWindowId && w.type === 'normal')
        .map(w => w.id);
    
    for (const wid of windowsToClose) await chrome.windows.remove(wid);
    
    checkBrowserState(); 
}

async function handlePlagio(reason) {
  if (!isExamActive) return;
  isExamActive = false;
  
  getCsrfTokenAndFetch(activeExamenId); 
  sendNativeMessage({ command: 'STOP_MONITORING' }); 

  if (activeExamenId) {
      chrome.storage.local.set({
          plagioFlag: { examenId: activeExamenId, reason: reason }
      });
  }

  chrome.tabs.sendMessage(examTabId, { type: "PLAGIO_ALERT", reason: reason });
}

async function getCsrfTokenAndFetch(examen_id) {
    if (!examen_id) return;
    try {
        // 1. CAMBIO: Buscar la cookie en el dominio real (HTTPS)
        const cookie = await chrome.cookies.get({ 
            url: 'https://examen.asantosb.dev', 
            name: 'csrftoken' 
        });
        
        if (!cookie) {
            console.error("No se encontró cookie CSRF.");
            return;
        }
        
        // 2. CAMBIO: Enviar la cancelación al servidor real
        await fetch('https://examen.asantosb.dev/exam/cancel/', {
            method: 'POST',
            headers: { 'X-CSRFToken': cookie.value, 'Content-Type': 'application/json' },
            body: JSON.stringify({ 'examen_id': examen_id })
        });
    } catch (error) { console.error(error); }
}