// Product Forge - Gemini Extension Popup Script

// Intent change handler
document.getElementById('intent').addEventListener('change', function() {
  const intent = this.value;
  document.getElementById('project-name-group').style.display = 
    (intent === 'new_project' || intent === 'new_project_quick') ? 'block' : 'none';
  document.getElementById('target-project-group').style.display = 
    (intent === 'modify_project' || intent === 'add_context') ? 'block' : 'none';
  
  if (intent === 'modify_project' || intent === 'add_context') {
    loadProjects();
  }
});

// Load projects from factory
async function loadProjects() {
  const settings = await chrome.storage.sync.get(['apiUrl', 'apiKey']);
  const apiUrl = settings.apiUrl || 'http://localhost:8000';
  const apiKey = settings.apiKey || '';

  try {
    const response = await fetch(`${apiUrl}/api/v1/projects`, {
      headers: { 'Authorization': `Bearer ${apiKey}` }
    });
    const data = await response.json();
    
    const select = document.getElementById('target-project');
    select.innerHTML = '<option value="">Select project...</option>';
    
    (data.projects || []).forEach(proj => {
      const option = document.createElement('option');
      option.value = proj.name;
      option.textContent = proj.name;
      select.appendChild(option);
    });
  } catch (error) {
    console.error('Failed to load projects:', error);
  }
}

// Send conversation
async function sendConversation() {
  const btn = document.getElementById('send-btn');
  const statusContainer = document.getElementById('status-container');
  
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>Sending...';

  // Get conversation from content script
  chrome.tabs.query({ active: true, currentWindow: true }, async (tabs) => {
    try {
      const response = await chrome.tabs.sendMessage(tabs[0].id, { type: 'EXTRACT_CONVERSATION' });
      
      if (!response || !response.messages || response.messages.length === 0) {
        showStatus('No messages found in conversation', 'error');
        btn.disabled = false;
        btn.innerHTML = 'Send to Factory';
        return;
      }

      // Send to factory via background script
      const intent = document.getElementById('intent').value;
      const projectName = document.getElementById('project-name').value;
      const targetProject = document.getElementById('target-project').value;

      const result = await chrome.runtime.sendMessage({
        type: 'SEND_TO_FACTORY',
        data: {
          messages: response.messages,
          title: response.title || document.title,
          intent: intent,
          projectName: projectName,
          targetProject: targetProject,
          url: tabs[0].url
        }
      });

      if (result.success) {
        showStatus(`Sent! ID: ${result.result.id}`, 'success');
        loadSentList();
      } else {
        showStatus(`Error: ${result.error}`, 'error');
      }
    } catch (error) {
      showStatus(`Failed: ${error.message}`, 'error');
    }

    btn.disabled = false;
    btn.innerHTML = 'Send to Factory';
  });
}

// Show status message
function showStatus(message, type) {
  const container = document.getElementById('status-container');
  container.innerHTML = `<div class="status status-${type}">${message}</div>`;
  setTimeout(() => { container.innerHTML = ''; }, 5000);
}

// Load sent conversations list
async function loadSentList() {
  const result = await chrome.runtime.sendMessage({ type: 'GET_SENT' });
  const list = document.getElementById('sent-list');
  
  if (!result.success || !result.conversations.length) {
    list.innerHTML = '<div style="color: #7a7a80; text-align: center; padding: 20px;">No conversations sent yet</div>';
    return;
  }

  list.innerHTML = result.conversations.slice(0, 10).map(conv => `
    <div class="sent-item">
      <div class="sent-title">${escapeHtml(conv.title)}</div>
      <div class="sent-meta">${conv.status} &middot; ${conv.intent} &middot; ${timeAgo(conv.sentAt)}</div>
    </div>
  `).join('');
}

// Open settings page
function openSettings() {
  chrome.runtime.openOptionsPage();
}

// Helper: escape HTML
function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// Helper: time ago
function timeAgo(dateStr) {
  if (!dateStr) return '';
  const now = new Date();
  const then = new Date(dateStr);
  const diff = Math.floor((now - then) / 1000);
  
  if (diff < 60) return 'just now';
  if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
  if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
  return Math.floor(diff / 86400) + 'd ago';
}

// Initialize
loadSentList();
