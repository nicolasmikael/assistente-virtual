document.addEventListener("DOMContentLoaded", () => {
  const chatContainer = document.getElementById("chat-container");
  const userInput = document.getElementById("user-input");
  const sendButton = document.getElementById("send-button");

  // Adiciona mensagem inicial de boas-vindas
  addMessage(
    `Olá! 👋 Sou o assistente virtual da loja. Como posso ajudar você hoje?

Posso te ajudar com:
• Busca de produtos
• Informações sobre políticas da loja
• Consulta de pedidos
• Recomendações personalizadas

É só me dizer o que você precisa! 😊`,
    false
  );

  // Função para adicionar mensagem ao chat
  function addMessage(content, isUser = false) {
    const messageDiv = document.createElement("div");
    messageDiv.className = `message ${
      isUser ? "user-message" : "assistant-message"
    }`;
    messageDiv.textContent = content;
    chatContainer.querySelector(".space-y-4").appendChild(messageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
  }

  // Função para mostrar indicador de digitação
  function showTypingIndicator() {
    const indicator = document.createElement("div");
    indicator.className = "typing-indicator";
    indicator.innerHTML = `
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
        `;
    chatContainer.querySelector(".space-y-4").appendChild(indicator);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    return indicator;
  }

  // Função para enviar mensagem
  async function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;

    // Adiciona mensagem do usuário
    addMessage(message, true);
    userInput.value = "";

    // Mostra indicador de digitação
    const typingIndicator = showTypingIndicator();

    try {
      // Envia mensagem para o servidor
      const response = await fetch("/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ content: message }),
      });

      if (!response.ok) {
        throw new Error("Erro na comunicação com o servidor");
      }

      const data = await response.json();

      // Remove indicador de digitação
      typingIndicator.remove();

      // Adiciona resposta do assistente
      addMessage(data.response);
    } catch (error) {
      // Remove indicador de digitação
      typingIndicator.remove();

      // Mostra mensagem de erro
      addMessage(
        "Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente."
      );
      console.error("Erro:", error);
    }
  }

  // Event listeners
  sendButton.addEventListener("click", sendMessage);
  userInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") {
      sendMessage();
    }
  });

  // Foco inicial no input
  userInput.focus();
});
