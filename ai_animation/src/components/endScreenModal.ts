import { gameState } from '../gameState';

interface EndScreenModalOptions {
  totalGamesPlayed: number;
  onRestart?: () => void;
}

let endScreenModalOverlay: HTMLElement | null = null;

/**
 * Shows an end screen modal when all games have been completed
 * @param options Configuration for the end screen modal
 */
export function showEndScreenModal(options: EndScreenModalOptions): void {
  const { totalGamesPlayed, onRestart } = options;

  // Close any existing modal
  closeEndScreenModal();

  // Create overlay
  endScreenModalOverlay = createEndScreenOverlay();

  // Create modal container
  const modalContainer = createEndScreenContainer(totalGamesPlayed);

  // Add close button if not in playing mode
  if (!gameState.isPlaying) {
    const closeButton = createCloseButton();
    modalContainer.appendChild(closeButton);
  }

  // Add to overlay
  endScreenModalOverlay.appendChild(modalContainer);
  document.body.appendChild(endScreenModalOverlay);

  // Set up event listeners
  setupEventListeners(onRestart);

  // Auto-restart after 5 seconds
  setTimeout(() => {
    closeEndScreenModal();
    onRestart?.();
  }, 5000);
}

/**
 * Closes the end screen modal
 */
export function closeEndScreenModal(): void {
  if (endScreenModalOverlay) {
    endScreenModalOverlay.classList.add('fade-out');
    setTimeout(() => {
      if (endScreenModalOverlay?.parentNode) {
        endScreenModalOverlay.parentNode.removeChild(endScreenModalOverlay);
      }
      endScreenModalOverlay = null;
    }, 300);
  }
}

/**
 * Creates the main overlay element
 */
function createEndScreenOverlay(): HTMLElement {
  const overlay = document.createElement('div');
  overlay.className = 'end-screen-modal-overlay';
  overlay.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0, 0, 0, 0.9);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 2000;
    opacity: 0;
    transition: opacity 0.5s ease;
  `;

  // Add fade-out class styles
  const style = document.createElement('style');
  style.textContent = `
    .end-screen-modal-overlay.fade-out {
      opacity: 0 !important;
      transition: opacity 0.3s ease;
    }
  `;
  document.head.appendChild(style);

  // Trigger fade in
  setTimeout(() => overlay.style.opacity = '1', 10);

  return overlay;
}

/**
 * Creates the main end screen container
 */
function createEndScreenContainer(totalGamesPlayed: number): HTMLElement {
  const container = document.createElement('div');
  container.className = 'end-screen-modal-container';
  container.style.cssText = `
    background: radial-gradient(ellipse at center, #2a1f1f 0%, #1a1015 100%);
    border: 5px solid #8b7355;
    border-radius: 12px;
    box-shadow: 0 0 40px rgba(255, 215, 0, 0.6);
    width: 90%;
    max-width: 600px;
    position: relative;
    padding: 40px;
    text-align: center;
    font-family: "Book Antiqua", Palatino, serif;
    color: #f0e6d2;
    animation: endScreenGlow 3s ease-in-out infinite alternate;
  `;

  // Add glow animation
  const style = document.createElement('style');
  style.textContent = `
    @keyframes endScreenGlow {
      0% { box-shadow: 0 0 40px rgba(255, 215, 0, 0.6); }
      100% { box-shadow: 0 0 60px rgba(255, 215, 0, 0.8); }
    }
  `;
  document.head.appendChild(style);

  // Crown/completion icon
  const crownElement = document.createElement('div');
  crownElement.textContent = '👑';
  crownElement.style.cssText = `
    font-size: 64px;
    margin-bottom: 20px;
    animation: float 3s ease-in-out infinite;
  `;

  // Add float animation
  const floatStyle = document.createElement('style');
  floatStyle.textContent = `
    @keyframes float {
      0%, 100% { transform: translateY(0px); }
      50% { transform: translateY(-10px); }
    }
  `;
  document.head.appendChild(floatStyle);

  // Title
  const titleElement = document.createElement('h1');
  titleElement.textContent = 'SERIES COMPLETE!';
  titleElement.style.cssText = `
    margin: 0 0 20px 0;
    color: #ffd700;
    font-size: 42px;
    font-weight: bold;
    text-shadow: 3px 3px 6px rgba(0,0,0,0.7);
    letter-spacing: 2px;
  `;

  // Completion message
  const messageElement = document.createElement('h2');
  messageElement.textContent = `All ${totalGamesPlayed} games completed!`;
  messageElement.style.cssText = `
    margin: 0 0 30px 0;
    color: #f0e6d2;
    font-size: 24px;
    font-weight: normal;
    text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
  `;

  // Restart countdown
  const countdownElement = document.createElement('div');
  countdownElement.style.cssText = `
    background: linear-gradient(90deg, #4a4a4a 0%, #2a2a2a 100%);
    color: #ffd700;
    padding: 15px 25px;
    border-radius: 25px;
    display: inline-block;
    font-size: 18px;
    font-weight: bold;
    margin-bottom: 20px;
    border: 2px solid #8b7355;
    box-shadow: 0 4px 8px rgba(0,0,0,0.4);
  `;

  // Animate countdown
  let countdown = 5;
  countdownElement.textContent = `Restarting series in ${countdown} seconds...`;
  
  const countdownInterval = setInterval(() => {
    countdown--;
    if (countdown > 0) {
      countdownElement.textContent = `Restarting series in ${countdown} seconds...`;
    } else {
      countdownElement.textContent = 'Restarting now...';
      clearInterval(countdownInterval);
    }
  }, 1000);

  // Thank you message
  const thankYouElement = document.createElement('div');
  thankYouElement.textContent = 'Thank you for watching the AI Diplomacy series!';
  thankYouElement.style.cssText = `
    color: #c4b998;
    font-size: 16px;
    font-style: italic;
    margin-top: 20px;
  `;

  // Assemble container
  container.appendChild(crownElement);
  container.appendChild(titleElement);
  container.appendChild(messageElement);
  container.appendChild(countdownElement);
  container.appendChild(thankYouElement);

  return container;
}

/**
 * Creates a close button
 */
function createCloseButton(): HTMLElement {
  const button = document.createElement('button');
  button.textContent = '×';
  button.className = 'end-screen-close-button';
  button.style.cssText = `
    position: absolute;
    top: 15px;
    right: 20px;
    background: none;
    border: none;
    font-size: 40px;
    color: #8b7355;
    cursor: pointer;
    padding: 0;
    width: 40px;
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    transition: all 0.2s ease;
  `;

  button.addEventListener('mouseenter', () => {
    button.style.color = '#ffd700';
    button.style.transform = 'scale(1.1)';
    button.style.backgroundColor = 'rgba(255, 255, 255, 0.1)';
  });

  button.addEventListener('mouseleave', () => {
    button.style.color = '#8b7355';
    button.style.transform = 'scale(1)';
    button.style.backgroundColor = 'transparent';
  });

  return button;
}

/**
 * Sets up event listeners for the end screen modal
 */
function setupEventListeners(onRestart?: () => void): void {
  if (!endScreenModalOverlay) return;

  const closeButton = endScreenModalOverlay.querySelector('.end-screen-close-button');
  const handleClose = () => {
    closeEndScreenModal();
    onRestart?.();
  };

  // Close button click (only if not in playing mode)
  if (!gameState.isPlaying) {
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
    endScreenModalOverlay.addEventListener('click', (e) => {
      if (e.target === endScreenModalOverlay) {
        handleClose();
      }
    });
  }
}