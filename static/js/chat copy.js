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
    function addMessageToChat(type, content) {
        console.log('Adding message:', { type, content });
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message`;

        if (type === 'error') {
            messageDiv.innerHTML = `<div class="error-message">${content}</div>`;
        } else if (content instanceof HTMLElement) {
            messageDiv.appendChild(content);
        } else {
            messageDiv.textContent = content;
        }

        chatBox.appendChild(messageDiv);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    // Property display functions
    function formatPropertyCard(propertyData) {
        return `
            <div class="property-card">
                <div class="property-image">
                    <img src="${propertyData.image || '/static/images/property-placeholder.jpg'}" 
                         alt="${propertyData.title || 'Propiedad'}"
                         onerror="this.src='/static/images/property-placeholder.jpg'">
                    <div class="property-tags">
                        ${propertyData.operation ? `
                            <span class="tag operation-tag">${propertyData.operation}</span>
                        ` : ''}
                        ${propertyData.price ? `
                            <span class="tag price-tag">$${propertyData.price}</span>
                        ` : ''}
                    </div>
                </div>
                <div class="property-content">
                    <h3 class="property-title">${propertyData.title || 'Sin título'}</h3>
                    <div class="property-features">
                        ${propertyData.type ? `
                            <div class="feature-item">
                                <i class="fas fa-home"></i>
                                <span>${propertyData.type}</span>
                            </div>
                        ` : ''}
                        ${propertyData.rooms ? `
                            <div class="feature-item">
                                <i class="fas fa-door-open"></i>
                                <span>${propertyData.rooms} Amb.</span>
                            </div>
                        ` : ''}
                        ${propertyData.surface ? `
                            <div class="feature-item">
                                <i class="fas fa-ruler-combined"></i>
                                <span>${propertyData.surface} m²</span>
                            </div>
                        ` : ''}
                        ${propertyData.expenses ? `
                            <div class="feature-item">
                                <i class="fas fa-money-bill"></i>
                                <span>Exp: $${propertyData.expenses}</span>
                            </div>
                        ` : ''}
                    </div>
                    ${propertyData.description ? `
                        <div class="property-description">
                            ${propertyData.description}
                        </div>
                    ` : ''}
                    <a href="${propertyData.url}" 
                       class="property-button" 
                       target="_blank"
                       rel="noopener noreferrer">
                        Ver más detalles
                        <i class="fas fa-external-link-alt"></i>
                    </a>
                </div>
            </div>
        `;
    }

    function parsePropertyText(text) {
        console.log('Raw property text:', text);

        // Split by numbered items and filter out empty/intro text
        const properties = text.split(/\d+\.\s+\*\*/).slice(1);
        
        return properties.map(property => {
            // Extract title from first line (handles all property types)
            const title = property.match(/^([^*]+)\*\*/)?.[1]?.trim();
            
            // Get property type from title
            const typeMatch = title?.match(/(departamento|casa|ph|local|oficina)/i);
            const propertyType = typeMatch ? 
                typeMatch[1].charat(0).toUpperCase() + typeMatch[1].slice(1).toLowerCase() : 
                'Propiedad';

            // Get operation type from context
            const operationType = text.toLowerCase().includes('venta') ? 'Venta' : 'Alquiler';
            
            // Parse details with improved regex patterns
            const data = {
                title: title,
                price: property.match(/Precio:\s*\$([0-9,.]+)/)?.[1]?.trim(),
                surface: property.match(/Superficie:\s*([0-9,.]+)\s*m²/)?.[1]?.trim(),
                expenses: property.match(/Expensas:\s*\$([0-9,.]+)/)?.[1]?.trim(),
                // Fix image extraction to capture all possible formats
                image: property.match(/!\[(?:Imagen|Ver imagen|Ver imagen y más detalles)\]\((https:\/\/[^\)]+)\)/)?.[1],
                // Fix link extraction to capture all possible formats
                link: property.match(/\[(?:Ver más|Más información|Ver detalles)\]\((https:\/\/[^\)]+)\)/)?.[1],
                type: propertyType,
                operation: operationType,
                // Optional: extract rooms if available
                rooms: property.match(/(\d+)\s*(?:amb|ambientes)/i)?.[1],
                // Optional: extract description if available
                description: property.match(/Descripción:\s*([^\n]+)/)?.[1]?.trim()
            };

            // Debug logging with extended info
            console.log('Parsed property data:', {
                ...data,
                hasImage: Boolean(data.image),
                hasLink: Boolean(data.link),
                imageMatches: [
                    property.match(/!\[Imagen\]\((https:\/\/[^\)]+)\)/),
                    property.match(/!\[Ver imagen\]\((https:\/\/[^\)]+)\)/),
                    property.match(/imagen:\s*(https:\/\/[^\s\n]+)/)
                ],
                linkMatches: [
                    property.match(/\[Ver más\]\((https:\/\/[^\)]+)\)/),
                    property.match(/\[Más información\]\((https:\/\/[^\)]+)\)/),
                    property.match(/\[.*?\]\((https:\/\/ficha\.info\/p\/[^\)]+)\)/)
                ]
            });
            
            return data;
        }).filter(prop => prop.title && (prop.price || prop.link));
    }

    function displayPropertyResults(content) {
        const propertiesContainer = document.createElement('div');
        propertiesContainer.className = 'property-grid';

        const properties = parsePropertyText(content);
        console.log('Parsed properties:', properties);

        if (properties.length === 0) {
            console.warn('No properties found to display');
            return propertiesContainer;
        }

        properties.forEach(propertyData => {
            const card = formatPropertyCard(propertyData);
            propertiesContainer.innerHTML += card;
        });

        return propertiesContainer;
    }

    // Chat handling function
    async function handleChat(userMessage) {
        try {
            // Type checking and validation
            if (!userMessage || typeof userMessage !== 'string') {
                throw new Error('El mensaje debe ser texto');
            }

            const messageText = userMessage.trim();
            if (!messageText) {
                throw new Error('El mensaje no puede estar vacío');
            }

            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message: messageText,
                    thread_id: window.currentThreadId || null
                })
            });

            const data = await response.json();
            
            if (data.status === 'success') {
                window.currentThreadId = data.thread_id;
                return data.response;
            }

            throw new Error(data.error || 'Error en la comunicación');

        } catch (error) {
            console.error('Chat error:', error);
            throw error;
        }
    }

    function displayProperties(properties) {
        const container = document.createElement('div');
        container.className = 'property-grid';

        properties.forEach(prop => {
            container.innerHTML += `
                <div class="property-card">
                    <div class="property-image">
                        <img src="${prop.image || '/static/images/property-placeholder.jpg'}" 
                             alt="${prop.title || 'Propiedad'}"
                             onerror="this.src='/static/images/property-placeholder.jpg'">
                        <div class="property-tags">
                            <span class="tag operation-tag">${prop.operation || 'Alquiler'}</span>
                            <span class="tag price-tag">$${prop.price?.toLocaleString() || 'Consultar'}</span>
                        </div>
                    </div>
                    <div class="property-content">
                        <h3 class="property-title">${prop.title || 'Sin título'}</h3>
                        <div class="property-features">
                            ${prop.rooms ? `
                                <div class="feature-item">
                                    <i class="fas fa-door-open"></i>
                                    <span>${prop.rooms} Amb.</span>
                                </div>
                            ` : ''}
                            ${prop.surface ? `
                                <div class="feature-item">
                                    <i class="fas fa-ruler-combined"></i>
                                    <span>${prop.surface} m²</span>
                                </div>
                            ` : ''}
                            ${prop.expenses ? `
                                <div class="feature-item">
                                    <i class="fas fa-money-bill"></i>
                                    <span>Exp: $${prop.expenses.toLocaleString()}</span>
                                </div>
                            ` : ''}
                        </div>
                        ${prop.description ? `
                            <div class="property-description">
                                ${prop.description}
                            </div>
                        ` : ''}
                        <a href="${prop.link}" class="property-button" target="_blank">
                            <i class="fas fa-external-link-alt"></i>
                            Ver más detalles
                        </a>
                    </div>
                </div>
            `;
        });

        return container;
    }

    // Event listeners
    chatForm.addEventListener('submit', handleChat);
    messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleChat(e);
    });
});

// Add message to chat
async function handleChatResponse(response) {
    // Check if response contains markdown-formatted properties
    if (response.includes('**') && response.includes('![Imagen]')) {
        // Parse the markdown response
        const properties = parseMarkdownProperties(response);
        return createPropertyGrid(properties);
    }
    
    // Regular text message
    const messageDiv = document.createElement('div');
    messageDiv.textContent = response;
    return messageDiv;
}

function parseMarkdownProperties(markdown) {
    const propertyTexts = markdown.split(/\d+\.\s+\*\*/).filter(text => text.trim());
    
    return propertyTexts.map(propText => {
        // Extract property details using regex
        const titleMatch = propText.match(/^([^*]+)\*\*/);
        const priceMatch = propText.match(/Precio:\s*ARS\s*([\d,]+)/);
        const surfaceMatch = propText.match(/Superficie:\s*([\d.]+)\s*m²/);
        const expensesMatch = propText.match(/Expensas:\s*ARS\s*([\d,]+)/);
        const imageMatch = propText.match(/!\[Imagen\]\((https:\/\/[^\)]+)\)/);
        // Updated URL regex to capture both direct and short URLs
        const linkMatch = propText.match(/\[(?:Más información|Ver más|Ver detalles)\]\((https:\/\/[^\)]+|\/p\/[^\)]+)\)/);
        const addressMatch = propText.match(/Dirección:\s*([^\n-]+)/);

        return {
            title: titleMatch ? titleMatch[1].trim() : '',
            price: priceMatch ? `ARS ${priceMatch[1]}` : 'Consultar',
            surface: surfaceMatch ? `${surfaceMatch[1]} m²` : '',
            expenses: expensesMatch ? `ARS ${expensesMatch[1]}` : '',
            image_url: imageMatch ? imageMatch[1] : '/static/images/property-placeholder.jpg',
            // If URL is a short path, convert to full URL
            url: linkMatch ? 
                (linkMatch[1].startsWith('http') ? 
                    linkMatch[1] : 
                    `https://ficha.info${linkMatch[1]}`
                ) : '#',
            address: addressMatch ? addressMatch[1].trim() : ''
        };
    });
}

function createPropertyGrid(properties) {
    const container = document.createElement('div');
    container.className = 'properties-grid';

    properties.forEach(prop => {
        // Ensure we have a valid URL from Tokko
        const propertyUrl = prop.url.startsWith('http') ? 
            prop.url : `https://ficha.info/p/${prop.url}`;

        const propertyCard = document.createElement('div');
        propertyCard.className = 'property-card';
        propertyCard.innerHTML = `
            <div class="property-image">
                <img src="${prop.image_url}" alt="${prop.title}" 
                     onerror="this.src='/static/images/property-placeholder.jpg'">
                <div class="property-tags">
                    <span class="tag operation-tag">Alquiler</span>
                    <span class="tag price-tag">${prop.price}</span>
                </div>
            </div>
            <div class="property-content">
                <h3 class="property-title">${prop.title}</h3>
                <div class="property-location">
                    <i class="fas fa-map-marker-alt"></i>
                    <span>${prop.address}</span>
                </div>
                <div class="property-details">
                    ${prop.surface ? `
                        <div class="detail-item">
                            <i class="fas fa-ruler-combined"></i>
                            <span>${prop.surface}</span>
                        </div>
                    ` : ''}
                    ${prop.expenses ? `
                        <div class="detail-item">
                            <i class="fas fa-money-bill-wave"></i>
                            <span>Expensas: ${prop.expenses}</span>
                        </div>
                    ` : ''}
                </div>
                <a href="${propertyUrl}" 
                   class="property-button" 
                   target="_blank" 
                   rel="noopener noreferrer">
                    Ver más detalles
                    <i class="fas fa-external-link-alt"></i>
                </a>
            </div>
        `;
        container.appendChild(propertyCard);
    });

    return container;
}

// Update addMessage function
async function addMessage(response, type = 'user') {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;

    if (type === 'assistant') {
        const contentDiv = await handleChatResponse(response);
        messageDiv.appendChild(contentDiv);
    } else {
        messageDiv.textContent = response;
    }

    document.getElementById('chat-messages').appendChild(messageDiv);
    messageDiv.scrollIntoView({ behavior: 'smooth' });
}

// Handle chat submission
async function handleChat(event) {
    event.preventDefault();
    
    const messageText = messageInput.value.trim();
    if (!messageText) return;

    try {
        addMessageToChat('user', messageText);
        messageInput.value = '';

        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ content: messageText })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Error en el servidor');
        }

        const data = await response.json();
        addMessageToChat('assistant', data.response);
    } catch (error) {
        console.error('Chat error:', error);
        addMessageToChat('error', 'Lo siento, hubo un error. Por favor, intentá nuevamente.');
    }
}

// Form submit handler
chatForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    
    const message = messageInput.value.trim();
    if (!message) return;

    try {
        await addMessage(message, 'user');
        messageInput.value = '';
        messageInput.focus();

        const response = await handleChat(message);
        await addMessage(response, 'assistant');

    } catch (error) {
        console.error('Chat error:', error);
        await addMessage('❌ ' + error.message, 'error');
    }
});

// Update chat form submission
chatForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    
    const input = document.getElementById('message-input');
    const message = input.value.trim();
    
    if (!message) return;

    try {
        // Add user message
        addMessage(message, 'user');
        
        // Clear input
        input.value = '';
        
        // Add typing indicator
        const typingDiv = document.createElement('div');
        typingDiv.className = 'typing-indicator';
        typingDiv.innerHTML = '<span></span><span></span><span></span>';
        document.getElementById('chat-messages').appendChild(typingDiv);
        
        // Get response
        const response = await handleChat(message);
        
        // Remove typing indicator
        typingDiv.remove();
        
        // Add assistant response
        addMessage(response, 'assistant');

    } catch (error) {
        console.error('Chat error:', error);
        addMessage('Error: ' + error.message, 'error');
    }
});

// Single chat submission handler
async function handleChat(event) {
    event.preventDefault();
    
    const messageText = messageInput.value.trim();
    if (!messageText) return;

    try {
        // Add user message
        addMessage(messageText, 'user');
        
        // Clear input and disable
        messageInput.value = '';
        messageInput.disabled = true;
        sendButton.disabled = true;
        
        // Add typing indicator
        const typingDiv = document.createElement('div');
        typingDiv.className = 'typing-indicator';
        typingDiv.innerHTML = '<span></span><span></span><span></span>';
        chatBox.appendChild(typingDiv);
        
        // Get response
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                content: messageText,
                thread_id: window.currentThreadId || null
            })
        });

        // Remove typing indicator
        typingDiv.remove();

        const data = await response.json();
        
        if (response.ok && data.status === 'success') {
            await addMessage(data.response, 'assistant');
            if (data.thread_id) {
                window.currentThreadId = data.thread_id;
            }
        } else {
            throw new Error(data.error || 'Error en el servidor');
        }
    } catch (error) {
        console.error('Chat error:', error);
        addMessage('Error: ' + error.message, 'error');
    } finally {
        // Re-enable input
        messageInput.disabled = false;
        sendButton.disabled = false;
        messageInput.focus();
    }
}

// Single event listener
chatForm.addEventListener('submit', handleChat);

// Enable form elements
messageInput.disabled = false;
sendButton.disabled = false;
