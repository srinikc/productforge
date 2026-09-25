// ==UserScript==
// @name         Claude - Send to Factory
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  Add "Send to Factory" button to Claude interface
// @author       You
// @match        https://claude.ai/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    // Wait for Claude to load
    function waitForClaude() {
        return new Promise((resolve) => {
            const check = () => {
                // Look for the main chat container
                const container = document.querySelector('[data-testid="chat-container"]') ||
                                 document.querySelector('.chat-container') ||
                                 document.querySelector('main');
                if (container) {
                    resolve(container);
                } else {
                    setTimeout(check, 500);
                }
            };
            check();
        });
    }

    // Extract conversation from Claude page
    function extractConversation() {
        const messages = [];
        
        // Try multiple selectors for Claude's message structure
        const userMessages = document.querySelectorAll('[data-testid^="user-message"]');
        const assistantMessages = document.querySelectorAll('[data-testid^="assistant-message"]');
        
        const count = Math.min(userMessages.length, assistantMessages.length);
        
        for (let i = 0; i < count; i++) {
            // User message
            const userContent = userMessages[i].querySelector('.markdown') || userMessages[i];
            messages.push({
                role: 'user',
                content: userContent.textContent.trim()
            });
            
            // Assistant message
            const modelContent = assistantMessages[i].querySelector('.markdown') || assistantMessages[i];
            messages.push({
                role: 'assistant',
                content: modelContent.textContent.trim()
            });
        }
        
        // Fallback: look for message bubbles by role
        if (messages.length === 0) {
            document.querySelectorAll('[role="user"], [role="assistant"]').forEach(el => {
                const isUser = el.getAttribute('role') === 'user';
                const contentEl = el.querySelector('.markdown') || el;
                messages.push({
                    role: isUser ? 'user' : 'assistant',
                    content: contentEl.textContent.trim()
                });
            });
        }
        
        return messages;
    }

    // Create "Send to Factory" button
    function createSendButton() {
        const btn = document.createElement('button');
        btn.id = 'pf-send-to-factory-claude';
        btn.innerHTML = '🚀 Send to Factory';
        btn.title = 'Send this conversation to Product Forge';
        btn.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 10000;
            padding: 10px 20px;
            background: #f97316;
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 6px;
        `;
        
        btn.addEventListener('mouseenter', () => {
            btn.style.background = '#ea6c0a';
            btn.style.transform = 'translateY(-2px)';
        });
        
        btn.addEventListener('mouseleave', () => {
            btn.style.background = '#f97316';
            btn.style.transform = 'translateY(0)';
        });
        
        btn.addEventListener('click', sendToFactory);
        return btn;
    }

    // Show status notification
    function showStatus(message, type) {
        // Remove existing status
        const existing = document.getElementById('pf-status-claude');
        if (existing) existing.remove();
        
        const status = document.createElement('div');
        status.id = 'pf-status-claude';
        status.style.cssText = `
            position: fixed;
            bottom: 80px;
            right: 20px;
            z-index: 10000;
            padding: 10px 16px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 600;
            color: white;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            transition: opacity 0.3s ease;
        `;
        
        if (type === 'success') {
            status.style.background = '#22c55e';
        } else if (type === 'error') {
            status.style.background = '#ef4444';
        } else {
            status.style.background = '#64748b';
        }
        
        status.textContent = message;
        document.body.appendChild(status);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            status.style.opacity = '0';
            setTimeout(() => status.remove(), 300);
        }, 5000);
    }

    // Main send function
    async function sendToFactory() {
        const btn = document.getElementById('pf-send-to-factory-claude');
        if (!btn) return;
        
        // Disable button during request
        btn.disabled = true;
        btn.innerHTML = '📤 Sending...';
        
        try {
            const messages = extractConversation();
            if (messages.length === 0) {
                showStatus('No messages found to send', 'error');
                return;
            }
            
            const title = document.querySelector('h1')?.textContent?.trim() || 
                       'Claude Conversation';
            
            const response = await fetch('http://localhost:8765/api/v1/intake', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    source_platform: 'claude',
                    intent: 'save_idea', // Default intent - could be made configurable
                    title: title,
                    messages: messages
                })
            });
            
            const result = await response.json();
            
            if (response.ok) {
                showStatus(`✅ Sent! ID: ${result.id.substring(0,8)}`, 'success');
            } else {
                showStatus(`❌ Error: ${result.detail || 'Unknown error'}`, 'error');
            }
        } catch (error) {
            showStatus(`❌ Failed: ${error.message}`, 'error');
        } finally {
            // Re-enable button
            btn.disabled = false;
            btn.innerHTML = '🚀 Send to Factory';
        }
    }

    // Initialize
    async function init() {
        try {
            await waitForClaude();
            
            // Add button to page
            const btn = createSendButton();
            document.body.appendChild(btn);
            
            console.log('🚀 Claude Send to Factory extension loaded');
        } catch (error) {
            console.error('Failed to initialize Claude extension:', error);
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
    const observer = new MutationObserver(() => {
        const url = location.href;
        if (url !== lastUrl) {
            lastUrl = url;
            setTimeout(init, 1000);
        }
    });
    
    observer.observe(document.body, { childList: true, subtree: true });
})();