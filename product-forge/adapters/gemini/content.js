// Product Forge - Gemini Content Script
// Injects "Send to Factory" button into Gemini UI

(function() {
  'use strict';

  // Wait for Gemini to load
  function waitForGemini() {
    return new Promise((resolve) => {
      const check = () => {
        // Look for Gemini's message container
        const container = document.querySelector('[data-message-author-role="model"]') ||
                         document.querySelector('.response-container') ||
                         document.querySelector('message-content');
        if (container) {
          resolve(container);
        } else {
          setTimeout(check, 500);
        }
      };
      check();
    });
  }

  // Extract conversation from Gemini page
  function extractConversation() {
    const messages = [];
    
    // Try multiple selectors for Gemini's message structure
    const userMessages = document.querySelectorAll('[data-message-author-role="user"]');
    const modelMessages = document.querySelectorAll('[data-message-author-role="model"]');
    
    userMessages.forEach((msg, i) => {
      const content = msg.querySelector('.markdown') || msg;
      messages.push({
        role: 'user',
        content: content.textContent.trim()
      });
      
      if (modelMessages[i]) {
        const modelContent = modelMessages[i].querySelector('.markdown') || modelMessages[i];
        messages.push({
          role: 'assistant',
          content: modelContent.textContent.trim()
        });
      }
    });

    // Fallback: try to extract from any visible messages
    if (messages.length === 0) {
      document.querySelectorAll('.message, [class*="message"]').forEach(msg => {
        const isUser = msg.classList.contains('user') || 
                      msg.querySelector('[data-message-author-role="user"]');
        const content = msg.textContent.trim();
        if (content) {
          messages.push({
            role: isUser ? 'user' : 'assistant',
            content: content
          });
        }
      });
    }

    return messages;
  }

  // Create "Send to Factory" button
  function createSendButton() {
    const btn = document.createElement('button');
    btn.id = 'pf-send-to-factory';
    btn.className = 'pf-send-btn';
    btn.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
        <polyline points="17 8 12 3 7 8"/>
        <line x1="12" y1="3" x2="12" y2="15"/>
      </svg>
      Send to Factory
    `;
    btn.title = 'Send this conversation to Product Forge';
    return btn;
  }

  // Create sending indicator
  function createSendingIndicator() {
    const indicator = document.createElement('div');
    indicator.id = 'pf-sending-indicator';
    indicator.className = 'pf-sending';
    indicator.innerHTML = `
      <div class="pf-spinner"></div>
      <span>Sending to Factory...</span>
    `;
    return indicator;
  }

  // Show status notification
  function showStatus(message, type) {
    const existing = document.getElementById('pf-status');
    if (existing) existing.remove();

    const status = document.createElement('div');
    status.id = 'pf-status';
    status.className = `pf-status pf-status-${type}`;
    status.textContent = message;
    document.body.appendChild(status);

    setTimeout(() => status.remove(), 5000);
  }

  // Main send function
  async function sendToFactory() {
    const settings = await chrome.storage.sync.get(['apiUrl', 'apiKey']);
    const apiUrl = settings.apiUrl || 'http://localhost:8765';
    const apiKey = settings.apiKey || '';

    const messages = extractConversation();
    if (messages.length === 0) {
      showStatus('No messages found to send', 'error');
      return;
    }

    // Show sending indicator
    const indicator = createSendingIndicator();
    document.body.appendChild(indicator);

    try {
      const response = await fetch(`${apiUrl}/api/v1/intake`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${apiKey}`
        },
        body: JSON.stringify({
          source_platform: 'gemini',
          intent: 'save_idea',
          title: document.title.replace(' - Gemini', '').trim(),
          messages: messages,
          metadata: {
            url: window.location.href,
            timestamp: new Date().toISOString()
          }
        })
      });

      const result = await response.json();
      
      if (response.ok) {
        showStatus(`Sent! ID: ${result.id}`, 'success');
        
        // Store in sent list
        const sent = await chrome.storage.local.get('sentConversations');
        const sentList = sent.sentConversations || [];
        sentList.unshift({
          id: result.id,
          title: document.title,
          status: result.status,
          sentAt: new Date().toISOString()
        });
        await chrome.storage.local.set({ sentConversations: sentList.slice(0, 50) });
      } else {
        showStatus(`Error: ${result.detail || 'Unknown error'}`, 'error');
      }
    } catch (error) {
      showStatus(`Failed: ${error.message}`, 'error');
    } finally {
      indicator.remove();
    }
  }

  // Initialize
  async function init() {
    // Wait for page to load
    await waitForGemini();

    // Add button to page
    const btn = createSendButton();
    btn.addEventListener('click', sendToFactory);
    
    // Find a good place to insert the button
    const target = document.querySelector('toolbar, [class*="toolbar"], [class*="action"]');
    if (target) {
      target.appendChild(btn);
    } else {
      // Fallback: add to bottom right
      document.body.appendChild(btn);
    }
  }

  // Start when page is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Re-initialize on navigation (SPA)
  let lastUrl = location.href;
  new MutationObserver(() => {
    const url = location.href;
    if (url !== lastUrl) {
      lastUrl = url;
      setTimeout(init, 1000);
    }
  }).observe(document, { subtree: true, childList: true });
})();
