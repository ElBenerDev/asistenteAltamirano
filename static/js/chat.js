// Global state
let currentThreadId = null;

document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const chatBox = document.getElementById('chat-box');
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');

    // Debug initialization
    console.group('Chat Initialization');
    console.log('DOM Elements:', {
        chatBox: Boolean(chatBox),
        messageInput: Boolean(messageInput),
        sendButton: Boolean(sendButton)
    });
    console.groupEnd();

    if (!chatBox || !messageInput || !sendButton) {
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
                    <a href="${propertyData.link ? propertyData.link : '#'}" 
                       class="property-button" 
                       target="_blank"
                       rel="noopener noreferrer"
                       ${!propertyData.link ? 'style="opacity: 0.5; pointer-events: none;"' : ''}>
                        <i class="fas fa-external-link-alt"></i>
                        Ver más detalles
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
                typeMatch[1].charAt(0).toUpperCase() + typeMatch[1].slice(1).toLowerCase() : 
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
    async function handleChat(event) {
        if (event) event.preventDefault();
        const message = messageInput.value.trim();

        if (!message) return;

        try {
            addMessageToChat('user', message);
            messageInput.value = '';

            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    message: message,
                    thread_id: currentThreadId 
                })
            });

            const data = await response.json();
            console.log('Server response:', data);

            if (data.status === 'error') {
                throw new Error(data.error || 'Unknown error');
            }

            // Update thread ID if provided
            if (data.thread_id) {
                currentThreadId = data.thread_id;
            }

            // Check if response contains property data
            if (data.response && data.response.includes('**')) {
                const propertyContainer = displayPropertyResults(data.response);
                addMessageToChat('assistant', propertyContainer);
            } else if (data.response) {
                // Regular conversation message
                addMessageToChat('assistant', data.response);
            } else {
                throw new Error('No response content');
            }

        } catch (error) {
            console.error('Chat error:', error);
            addMessageToChat('error', '❌ Error al procesar tu mensaje');
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
    sendButton.addEventListener('click', handleChat);
    messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleChat(e);
    });
});
