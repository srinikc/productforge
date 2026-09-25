# Factory Automation - Browser Scripts

## Overview

These browser userscripts add "Send to Factory" buttons directly to ChatGPT and Claude interfaces, enabling one-click sending of conversations to your Product Factory without manual copy-paste.

## Available Scripts

1. **ChatGPT** - `adapters/chatgpt/send-to-factory.user.js`
2. **Claude** - `adapters/claude/send-to-factory.user.js`
3. **Gemini** - Existing Chrome extension in `adapters/gemini/` (already provides this functionality)

## How It Works

Unlike the Custom GPT Action approach (which requires public HTTPS access), these scripts run **in your browser**:
- You interact with ChatGPT/Claude in your browser
- When you click "Send to Factory", the script runs in **your browser's context**
- Your browser makes the HTTP request directly to `localhost:8765/api/v1/intake`
- No tunneling or public URLs needed - works 100% locally

## Installation

### Option 1: Tampermonkey/Greasemonkey (Recommended)

1. Install [Tampermonkey](https://www.tampermonkey.net/) or [Greasemonkey](https://www.greasespot.net/) browser extension
2. Click the extension icon → "Create a new script"
3. **Delete the default content** and paste the entire script from:
   - For ChatGPT: `adapters/chatgpt/send-to-factory.user.js`
   - For Claude: `adapters/claude/send-to-factory.user.js`
4. Save the script
5. Visit [chat.openai.com](https://chat.openai.com) or [claude.ai](https://claude.ai)
6. You'll see a 🚀 **Send to Factory** button in the bottom-right corner
7. Click it to send the current conversation to your factory

### Option 2: Bookmarklet (Quick Test)

Create a bookmark with this URL (for ChatGPT):
```javascript
javascript:(function(){var s=document.createElement('script');s.src='https://raw.githubusercontent.com/yourusername/yourfactory/main/adapters/chatgpt/send-to-factory.user.js';document.body.appendChild(s);})();
```
(Replace with actual URL when hosted)

## Features

- ✅ **One-click sending** - No copy-paste needed
- ✅ **Automatic conversation extraction** - Gets messages from current chat
- ✅ **Visual feedback** - Success/error notifications
- ✅ **Works with existing factory** - Uses same `/api/v1/intake` endpoint
- ✅ **No server changes needed** - Pure client-side automation
- ✅ **SPA support** - Handles page navigation in chat interfaces
- ✅ **Error handling** - Shows meaningful error messages

## Usage Examples

After installation, you can:
1. Have a conversation in ChatGPT or Claude
2. Click the 🚀 **Send to Factory** button (bottom-right)
3. See a confirmation notification
4. Go to your factory dashboard → Inbox to review the conversation
5. Compile, approve, or promote as needed

## Customization

### Change Default Intent
Edit the script and change:
```javascript
intent: 'save_idea',
```
to any of: `save_idea`, `new_project`, `new_project_quick`, `modify_project`, `add_context`

### Add Project Name (for new_project intent)
Modify the JSON payload:
```javascript
body: JSON.stringify({
    source_platform: 'chatgpt',
    intent: 'new_project',
    project_name: 'my-awesome-project', // <-- Add this
    title: title,
    messages: messages
})
```

## Security Notes

- Scripts only run on chatgpt.com and claude.ai domains
- No data leaves your machine except the intentional factory API calls
- No external dependencies - all logic is self-contained
- Uses same API endpoint as manual methods - no additional attack surface

## Troubleshooting

### Button not appearing?
- Wait 5-10 seconds after page load
- Check browser console for errors (F12 → Console)
- Ensure you're on the correct domain (chat.openai.com or claude.ai)

### Not sending?
- Check that your factory server is running (`python pipeline_dashboard/serve.py`)
- Look for error notifications in bottom-right
- Check browser console for network errors
- Verify localhost:8765 is accessible in your browser

### Getting CORS errors?
- This shouldn't happen as you're making requests to localhost from localhost
- If you see CORS errors, you're likely trying to send from a different domain/protocol

## Comparison with Other Methods

| Method | Setup Complexity | Requires Public URL? | Automation Level | Works Offline? |
|--------|------------------|----------------------|------------------|----------------|
| **Browser Scripts** (this) | Low (install extension) | ❌ No | ⭐⭐⭐⭐⭐ (One-click) | ✅ Yes |
| **Manual Copy-Paste** | None | ❌ No | ⭐⭐ (Copy-paste) | ✅ Yes |
| **ChatGPT Custom GPT** | Medium (schema import) | ✅ Yes (HTTPS) | ⭐⭐⭐⭐ (Auto-call) | ❌ No |
| **ngrok/cloudflared Tunnel** | Medium (install+run) | ✅ Yes | ⭐⭐⭐⭐⭐ (Auto-call) | ❌ No |
| **Manual Form** | Very Low | ❌ No | ⭐⭐ (Copy-paste+submit) | ✅ Yes |

## Next Steps

For even more automation, consider:
1. **Keyboard shortcuts** - Add Ctrl+Enter to send
2. **Auto-send on conversation end** - Detect when AI finishes responding
3. **Intent detection** - Auto-choose intent based on conversation content
4. **Factory status indicator** - Show if server is online/offline
5. **History tracking** - Show recently sent conversations in popup

These scripts provide a solid foundation for factory automation that works reliably in restricted network environments where public HTTPS access isn't available.