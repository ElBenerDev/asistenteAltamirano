function formatPropertyCard(propertyData) {
    return `
        <div class="property-card">
            <div class="property-header">
                <i class="fas fa-building"></i>
                <h3 class="property-title">${propertyData.title}</h3>
            </div>
            
            <div class="property-location">
                <i class="fas fa-map-marker-alt"></i> ${propertyData.location}
            </div>
            
            <div class="property-details">
                <div class="detail-item">
                    <i class="fas fa-dollar-sign"></i> ${propertyData.price}
                </div>
                <div class="detail-item">
                    <i class="fas fa-bed"></i> ${propertyData.rooms} Ambientes
                </div>
                <div class="detail-item">
                    <i class="fas fa-bath"></i> ${propertyData.bathrooms} Baños
                </div>
                <div class="detail-item">
                    <i class="fas fa-ruler-combined"></i> ${propertyData.surface} m²
                </div>
            </div>
            
            ${propertyData.photos ? `
                <div class="property-photos">
                    ${propertyData.photos.map(photo => `
                        <img src="${photo}" alt="Propiedad" loading="lazy">
                    `).join('')}
                </div>
            ` : ''}
            
            <div class="property-description">
                <i class="fas fa-quote-left"></i> ${propertyData.description}
            </div>
            
            <a href="${propertyData.url}" class="view-more-btn" target="_blank">
                <i class="fas fa-external-link-alt"></i> Ver Más Detalles
            </a>
        </div>
    `;
}

function handlePropertyPhotos() {
    document.querySelectorAll('.property-photos img').forEach(img => {
        img.addEventListener('click', function() {
            const modal = document.createElement('div');
            modal.className = 'photo-modal';
            modal.innerHTML = `
                <div class="modal-content">
                    <img src="${this.src}" alt="Foto ampliada">
                    <button class="close-modal">&times;</button>
                </div>
            `;
            document.body.appendChild(modal);
            
            modal.querySelector('.close-modal').onclick = function() {
                modal.remove();
            };
            
            modal.onclick = function(e) {
                if (e.target === modal) {
                    modal.remove();
                }
            };
        });
    });
}

function addMessage(message, isUser) {
    const chatContainer = document.getElementById('chatContainer');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user-message' : 'assistant-message'}`;
    
    if (!isUser) {
        // Detectar si el mensaje contiene datos de propiedades
        if (message.includes('Propiedades Encontradas')) {
            const [chatResponse, ...properties] = message.split('🏡');
            
            // Agregar respuesta del asistente
            if (chatResponse.trim()) {
                const responseDiv = document.createElement('div');
                responseDiv.className = 'message assistant-message';
                responseDiv.innerHTML = `<i class="fas fa-robot me-2"></i>${chatResponse.trim()}`;
                chatContainer.appendChild(responseDiv);
            }
            
            // Agregar propiedades con formato
            properties.forEach(property => {
                const propertyDiv = document.createElement('div');
                propertyDiv.innerHTML = formatPropertyCard({
                    title: property.split('\n')[0],
                    // ... parse other property data
                });
                chatContainer.appendChild(propertyDiv);
            });
        } else {
            messageDiv.innerHTML = `<i class="fas fa-robot me-2"></i>${message}`;
            chatContainer.appendChild(messageDiv);
        }
        handlePropertyPhotos();
        
        // Make all links open in new tab
        messageDiv.querySelectorAll('a').forEach(link => {
            link.setAttribute('target', '_blank');
            link.setAttribute('rel', 'noopener noreferrer');
        });
    } else {
        messageDiv.innerHTML = `<i class="fas fa-user me-2"></i>${message}`;
        chatContainer.appendChild(messageDiv);
    }
    
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function sendMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();
    
    if (message) {
        addMessage(message, true);
        input.value = '';
        
        fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: message })
        })
        .then(response => response.json())
        .then(data => {
            addMessage(data.content, false);
        })
        .catch(error => {
            console.error('Error:', error);
            addMessage('Lo siento, ocurrió un error.', false);
        });
    }
}

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    // Handle Enter key
    document.getElementById('messageInput').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });

    // Prevent iOS bounce scroll
    document.body.addEventListener('touchmove', function(e) {
        if (e.target.closest('.chat-container')) return;
        e.preventDefault();
    }, { passive: false });

    // Adjust viewport on mobile keyboard
    const viewport = document.querySelector('meta[name=viewport]');
    if (window.visualViewport) {
        window.visualViewport.addEventListener('resize', function() {
            if (window.visualViewport.height < window.innerHeight) {
                viewport.setAttribute('content', 'width=device-width, initial-scale=1, maximum-scale=1');
            } else {
                viewport.setAttribute('content', 'width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no');
            }
        });
    }

    // Focus input on load for desktop
    if (window.innerWidth > 768) {
        document.getElementById('messageInput').focus();
    }
});