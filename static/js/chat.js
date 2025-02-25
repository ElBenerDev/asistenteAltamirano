document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const chatBox = document.getElementById('chat-box');
    const chatForm = document.getElementById('chat-form');
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');
    window.currentThreadId = null;

    console.group('Chat Initialization');
    console.log('DOM Elements:', {
        chatBox: Boolean(chatBox),
        messageInput: Boolean(messageInput),
        sendButton: Boolean(sendButton),
        chatForm: Boolean(chatForm)
    });
    console.groupEnd();

    if (!chatBox || !messageInput || !sendButton || !chatForm) {
        console.error('Required chat elements not found');
        return;
    }

    // Message display function
    function addMessageToChat(type, content, isHtml = false) {
        console.log('Adding message:', { type, isHtml });
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message`;
        
        if (isHtml) {
            console.log('Rendering as HTML');
            messageDiv.innerHTML = content;
            
            // Add click handlers to property cards
            messageDiv.querySelectorAll('.property-card').forEach(card => {
                const link = card.querySelector('.property-link');
                if (link) {
                    card.addEventListener('click', (e) => {
                        if (!e.target.closest('.property-link')) {
                            link.click();
                        }
                    });
                }
            });
        } else {
            console.log('Rendering as text');
            messageDiv.textContent = content;
        }
        
        chatBox.appendChild(messageDiv);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    // Handle chat submission
    async function handleChat(event) {
        event.preventDefault();
        console.group('Chat Request');
        
        try {
            const messageText = messageInput.value.trim();
            if (!messageText) return;
            
            // Show user message
            addMessageToChat('user', messageText);
            messageInput.value = '';
            
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    content: messageText,
                    thread_id: window.currentThreadId || null
                })
            });

            const data = await response.json();
            console.log('Response:', {
                isHtml: data.isHtml,
                contentLength: data.response?.length,
                hasPropertiesGrid: data.response?.includes('properties-grid')
            });

            if (response.ok && data.status === 'success') {
                addMessageToChat('assistant', data.response, data.isHtml);
                if (data.thread_id) window.currentThreadId = data.thread_id;
            } else {
                throw new Error(data.error || 'Error en el servidor');
            }
        } catch (error) {
            console.error('Error:', error);
            addMessageToChat('error', error.message);
        }
        
        console.groupEnd();
    }

    // Single event listener
    chatForm.addEventListener('submit', handleChat);

    // Enable form elements
    messageInput.disabled = false;
    sendButton.disabled = false;
});