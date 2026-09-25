// Product Forge - Gemini Extension Background Script

// Retry queue for failed sends
let retryQueue = [];
const MAX_RETRIES = 5;
const RETRY_DELAYS = [5000, 30000, 120000, 600000, 3600000]; // ms

// Handle messages from content script and popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'SEND_TO_FACTORY') {
    sendToFactory(message.data)
      .then(result => sendResponse({ success: true, result }))
      .catch(error => sendResponse({ success: false, error: error.message }));
    return true; // Keep message channel open for async response
  }

  if (message.type === 'GET_STATUS') {
    getConversationStatus(message.id)
      .then(result => sendResponse({ success: true, result }))
      .catch(error => sendResponse({ success: false, error: error.message }));
    return true;
  }

  if (message.type === 'GET_SENT') {
    chrome.storage.local.get('sentConversations', (data) => {
      sendResponse({ success: true, conversations: data.sentConversations || [] });
    });
    return true;
  }

  if (message.type === 'GET_PENDING') {
    sendResponse({ success: true, queue: retryQueue });
    return true;
  }
});

// Send conversation to factory
async function sendToFactory(data) {
  const settings = await chrome.storage.sync.get(['apiUrl', 'apiKey', 'defaultIntent']);
  const apiUrl = settings.apiUrl || 'http://localhost:8765';
  const apiKey = settings.apiKey || '';
  const defaultIntent = settings.defaultIntent || 'save_idea';

  const payload = {
    source_platform: 'gemini',
    intent: data.intent || defaultIntent,
    project_name: data.projectName || '',
    target_project_name: data.targetProject || '',
    title: data.title || 'Gemini Conversation',
    messages: data.messages || [],
    metadata: {
      url: data.url || '',
      timestamp: new Date().toISOString()
    }
  };

  try {
    const response = await fetch(`${apiUrl}/api/v1/intake`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`
      },
      body: JSON.stringify(payload)
    });

    const result = await response.json();

    if (response.ok) {
      // Store in sent list
      const sent = await chrome.storage.local.get('sentConversations');
      const sentList = sent.sentConversations || [];
      sentList.unshift({
        id: result.id,
        title: payload.title,
        status: result.status,
        intent: payload.intent,
        sentAt: new Date().toISOString()
      });
      await chrome.storage.local.set({ sentConversations: sentList.slice(0, 100) });

      return result;
    } else {
      throw new Error(result.detail || 'API error');
    }
  } catch (error) {
    // Add to retry queue
    addToRetryQueue({ ...payload, error: error.message });
    throw error;
  }
}

// Get conversation status
async function getConversationStatus(convId) {
  const settings = await chrome.storage.sync.get(['apiUrl', 'apiKey']);
  const apiUrl = settings.apiUrl || 'http://localhost:8765';
  const apiKey = settings.apiKey || '';

  const response = await fetch(`${apiUrl}/api/v1/intake/${convId}`, {
    headers: {
      'Authorization': `Bearer ${apiKey}`
    }
  });

  return await response.json();
}

// Retry queue management
function addToRetryQueue(item) {
  item.retryCount = (item.retryCount || 0) + 1;
  if (item.retryCount <= MAX_RETRIES) {
    item.nextRetry = Date.now() + RETRY_DELAYS[Math.min(item.retryCount - 1, RETRY_DELAYS.length - 1)];
    retryQueue.push(item);
    saveRetryQueue();
  }
}

async function saveRetryQueue() {
  await chrome.storage.local.set({ retryQueue });
}

async function loadRetryQueue() {
  const data = await chrome.storage.local.get('retryQueue');
  retryQueue = data.retryQueue || [];
}

// Process retry queue
async function processRetryQueue() {
  const now = Date.now();
  const toRetry = retryQueue.filter(item => item.nextRetry <= now);
  
  for (const item of toRetry) {
    try {
      await sendToFactory(item);
      retryQueue = retryQueue.filter(i => i !== item);
    } catch (error) {
      // Will be re-added to queue by sendToFactory
      retryQueue = retryQueue.filter(i => i !== item);
    }
  }
  
  await saveRetryQueue();
}

// Initialize
loadRetryQueue();
setInterval(processRetryQueue, 30000); // Check every 30 seconds
