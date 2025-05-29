import { gameState } from '../gameState';
import { config } from '../config';
import { getPowerDisplayName } from '../utils/powerNames';
import { PowerENUM } from '../types/map';

interface ConversationMessage {
  sender: string;
  recipient: string;
  message: string;
  time_sent?: string;
  [key: string]: any;
}

interface TwoPowerDialogueOptions {
  power1: string;
  power2: string;
  messages?: ConversationMessage[];
  title?: string;
  onClose?: () => void;
}

let dialogueOverlay: HTMLElement | null = null;

/**
 * Shows a dialogue box displaying conversation between two powers
 * @param options Configuration for the dialogue display
 */
export function showTwoPowerConversation(options: TwoPowerDialogueOptions): void {
  const { power1, power2, messages, title, onClose } = options;

  // Close any existing dialogue
  closeTwoPowerConversation();

  // Get messages to display - either provided or filtered from current phase
  const conversationMessages = messages || getMessagesBetweenPowers(power1, power2);

  if (conversationMessages.length === 0) {
    console.warn(`No messages found between ${power1} and ${power2}`);
    return;
  }

  // Create overlay
  dialogueOverlay = createDialogueOverlay();

  // Create dialogue container
  const dialogueContainer = createDialogueContainer(power1, power2, title);

  // Create conversation area
  const conversationArea = createConversationArea();
  dialogueContainer.appendChild(conversationArea);

  // Add close button
  const closeButton = createCloseButton();
  dialogueContainer.appendChild(closeButton);

  // Add to overlay
  dialogueOverlay.appendChild(dialogueContainer);
  document.body.appendChild(dialogueOverlay);

  // Set up event listeners
  setupEventListeners(onClose);

  // Animate messages
  animateMessages(conversationArea, conversationMessages, power1, power2);
}

/**
 * Closes the two-power conversation dialogue
 */
export function closeTwoPowerConversation(): void {
  if (dialogueOverlay) {
    dialogueOverlay.classList.add('fade-out');
    setTimeout(() => {
      if (dialogueOverlay?.parentNode) {
        dialogueOverlay.parentNode.removeChild(dialogueOverlay);
      }
      dialogueOverlay = null;
      gameState.isDisplayingMoment = false;
    }, 300);
  }
}

/**
 * Gets messages between two specific powers from current phase
 */
function getMessagesBetweenPowers(power1: string, power2: string): ConversationMessage[] {
  const currentPhase = gameState.gameData?.phases[gameState.phaseIndex];
  if (!currentPhase?.messages) return [];

  return currentPhase.messages.filter((msg) => {
    const sender = msg.sender?.toUpperCase();
    const recipient = msg.recipient?.toUpperCase();
    const p1 = power1.toUpperCase();
    const p2 = power2.toUpperCase();

    return (sender === p1 && recipient === p2) ||
      (sender === p2 && recipient === p1);
  }).sort((a, b) => {
    // Sort by time_sent if available, otherwise maintain original order
    if (a.time_sent && b.time_sent) {
      return a.time_sent > b.time_sent;
    }
    return 0;
  });
}

/**
 * Creates the main overlay element
 */
function createDialogueOverlay(): HTMLElement {
  const overlay = document.createElement('div');
  overlay.className = 'dialogue-overlay';
  overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-color: rgba(0, 0, 0, 0.7);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 1000;
        opacity: 0;
        transition: opacity 0.3s ease;
    `;

  // Trigger fade in
  setTimeout(() => overlay.style.opacity = '1', 10);

  return overlay;
}

/**
 * Creates the main dialogue container
 */
function createDialogueContainer(power1: string, power2: string, title?: string): HTMLElement {
  const container = document.createElement('div');
  container.className = 'dialogue-container';
  container.style.cssText = `
        background: radial-gradient(ellipse at center, #f7ecd1 0%, #dbc08c 100%);
        border: 3px solid #4f3b16;
        border-radius: 8px;
        box-shadow: 0 0 15px rgba(0,0,0,0.5);
        width: 80%;
        height: 80%;
        position: relative;
        padding: 20px;
        display: flex;
        flex-direction: column;
    `;

  // Add title
  const titleElement = document.createElement('h2');
  titleElement.textContent = title || `Conversation: ${getPowerDisplayName(power1 as PowerENUM)} & ${getPowerDisplayName(power2 as PowerENUM)}`;
  titleElement.style.cssText = `
        margin: 0 0 20px 0;
        text-align: center;
        color: #4f3b16;
        font-family: 'Times New Roman', serif;
        font-size: 24px;
        font-weight: bold;
    `;
  container.appendChild(titleElement);

  return container;
}

/**
 * Creates the conversation display area
 */
function createConversationArea(): HTMLElement {
  const area = document.createElement('div');
  area.className = 'conversation-area';
  area.style.cssText = `
        flex: 1;
        overflow-y: auto;
        padding: 10px;
        border: 2px solid #8b7355;
        border-radius: 5px;
        background: rgba(255, 255, 255, 0.3);
        display: flex;
        flex-direction: column;
        gap: 15px;
    `;

  return area;
}

/**
 * Creates a close button
 */
function createCloseButton(): HTMLElement {
  const button = document.createElement('button');
  button.textContent = '�';
  button.className = 'close-button';
  button.style.cssText = `
        position: absolute;
        top: 10px;
        right: 15px;
        background: none;
        border: none;
        font-size: 30px;
        color: #4f3b16;
        cursor: pointer;
        padding: 0;
        width: 30px;
        height: 30px;
        display: flex;
        align-items: center;
        justify-content: center;
    `;

  button.addEventListener('mouseenter', () => {
    button.style.color = '#8b0000';
    button.style.transform = 'scale(1.1)';
  });

  button.addEventListener('mouseleave', () => {
    button.style.color = '#4f3b16';
    button.style.transform = 'scale(1)';
  });

  return button;
}

/**
 * Sets up event listeners for the dialogue
 */
function setupEventListeners(onClose?: () => void): void {
  if (!dialogueOverlay) return;

  const closeButton = dialogueOverlay.querySelector('.close-button');
  const handleClose = () => {
    closeTwoPowerConversation();
    onClose?.();
  };

  // Close button click
  closeButton?.addEventListener('click', handleClose);

  // Escape key
  const handleKeydown = (e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      handleClose();
      document.removeEventListener('keydown', handleKeydown);
    }
  };
  document.addEventListener('keydown', handleKeydown);

  // Click outside to close
  dialogueOverlay.addEventListener('click', (e) => {
    if (e.target === dialogueOverlay) {
      handleClose();
    }
  });
}

/**
 * Animates the display of messages in the conversation
 */
async function animateMessages(
  container: HTMLElement,
  messages: ConversationMessage[],
  power1: string,
  power2: string
): Promise<void> {
  for (const message of messages) {
    const messageElement = createMessageElement(message, power1, power2);
    container.appendChild(messageElement);

    // Animate message appearance
    messageElement.style.opacity = '0';
    messageElement.style.transform = 'translateY(20px)';

    await new Promise(resolve => {
      setTimeout(() => {
        messageElement.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
        messageElement.style.opacity = '1';
        messageElement.style.transform = 'translateY(0)';

        // Scroll to bottom
        container.scrollTop = container.scrollHeight;

        setTimeout(resolve, 300 + (1000 / config.playbackSpeed));
      }, 100);
    });
  }
}

/**
 * Creates a message element for display
 */
function createMessageElement(message: ConversationMessage, power1: string, power2: string): HTMLElement {
  const messageDiv = document.createElement('div');
  const isFromPower1 = message.sender.toUpperCase() === power1.toUpperCase();

  messageDiv.className = `message ${isFromPower1 ? 'power1' : 'power2'}`;
  messageDiv.style.cssText = `
        display: flex;
        flex-direction: column;
        align-items: ${isFromPower1 ? 'flex-start' : 'flex-end'};
        margin: 5px 0;
    `;

  // Sender label
  const senderLabel = document.createElement('div');
  senderLabel.textContent = getPowerDisplayName(message.sender as PowerENUM);
  senderLabel.className = `power-${message.sender.toLowerCase()}`;
  senderLabel.style.cssText = `
        font-size: 12px;
        font-weight: bold;
        margin-bottom: 5px;
        color: #4f3b16;
    `;

  // Message bubble
  const messageBubble = document.createElement('div');
  messageBubble.textContent = message.message;
  messageBubble.style.cssText = `
        background: ${isFromPower1 ? '#e6f3ff' : '#fff3e6'};
        border: 2px solid ${isFromPower1 ? '#4a90e2' : '#e67e22'};
        border-radius: 15px;
        padding: 10px 15px;
        max-width: 70%;
        word-wrap: break-word;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    `;

  messageDiv.appendChild(senderLabel);
  messageDiv.appendChild(messageBubble);

  return messageDiv;
}
