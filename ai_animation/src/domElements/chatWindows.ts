import * as THREE from "three";
import { currentPower, gameState } from "../gameState";
import { config } from "../config";
import { advanceToNextPhase } from "../phase";

let faceIconCache = {}; // Cache for generated face icons

// Add a message counter to track sound effect frequency
let messageCounter = 0;
let chatWindows = {}; // Store chat window elements by power
// --- CHAT WINDOW FUNCTIONS ---
export function createChatWindows() {
  // Clear existing chat windows
  const chatContainer = document.getElementById('chat-container');
  chatContainer.innerHTML = '';
  chatWindows = {};

  // Create a chat window for each power (except the current power)
  const powers = ['AUSTRIA', 'ENGLAND', 'FRANCE', 'GERMANY', 'ITALY', 'RUSSIA', 'TURKEY'];

  // Filter out the current power for chat windows
  const otherPowers = powers.filter(power => power !== currentPower);

  // Add a GLOBAL chat window first
  createChatWindow('GLOBAL', true);

  // Create chat windows for each power except the current one
  otherPowers.forEach(power => {
    createChatWindow(power);
  });
}
// Modified to use 3D face icons properly
function createChatWindow(power, isGlobal = false) {
  const chatContainer = document.getElementById('chat-container');
  const chatWindow = document.createElement('div');
  chatWindow.className = 'chat-window';
  chatWindow.id = `chat-${power}`;
  chatWindow.style.position = 'relative'; // Add relative positioning for absolute child positioning

  // Create a slimmer header with appropriate styling
  const header = document.createElement('div');
  header.className = 'chat-header';

  // Adjust header to accommodate larger face icons
  header.style.display = 'flex';
  header.style.alignItems = 'center';
  header.style.padding = '4px 8px'; // Reduced vertical padding
  header.style.height = '24px'; // Explicit smaller height
  header.style.backgroundColor = 'rgba(78, 62, 41, 0.7)'; // Semi-transparent background
  header.style.borderBottom = '1px solid rgba(78, 62, 41, 1)'; // Solid bottom border

  // Create the title element
  const titleElement = document.createElement('span');
  if (isGlobal) {
    titleElement.style.color = '#ffffff';
    titleElement.textContent = 'GLOBAL';
  } else {
    titleElement.className = `power-${power.toLowerCase()}`;
    titleElement.textContent = power;
  }
  titleElement.style.fontWeight = 'bold'; // Make text more prominent
  titleElement.style.textShadow = '1px 1px 2px rgba(0,0,0,0.7)'; // Add text shadow for better readability
  header.appendChild(titleElement);

  // Create container for 3D face icon that floats over the header
  const faceHolder = document.createElement('div');
  faceHolder.style.width = '64px';
  faceHolder.style.height = '64px';
  faceHolder.style.position = 'absolute'; // Position absolutely
  faceHolder.style.right = '10px'; // From right edge
  faceHolder.style.top = '0px'; // ADJUSTED: Moved lower to align with the header
  faceHolder.style.cursor = 'pointer';
  faceHolder.style.borderRadius = '50%';
  faceHolder.style.overflow = 'hidden';
  faceHolder.style.boxShadow = '0 2px 5px rgba(0,0,0,0.5)';
  faceHolder.style.border = '2px solid #fff';
  faceHolder.style.zIndex = '10'; // Ensure it's above other elements
  faceHolder.id = `face-${power}`;

  // Generate the face icon and add it to the chat window (not header)
  generateFaceIcon(power).then(dataURL => {
    const img = document.createElement('img');
    img.src = dataURL;
    img.style.width = '100%';
    img.style.height = '100%';
    img.id = `face-img-${power}`; // Add ID for animation targeting

    // Add subtle idle animation
    setInterval(() => {
      if (!img.dataset.animating && Math.random() < 0.1) {
        idleAnimation(img);
      }
    }, 3000);

    faceHolder.appendChild(img);
  });

  // Create messages container with extra top padding to avoid overlap with floating head

  header.appendChild(faceHolder);

  // Create messages container
  const messagesContainer = document.createElement('div');
  messagesContainer.className = 'chat-messages';
  messagesContainer.id = `messages-${power}`;
  messagesContainer.style.paddingTop = '8px'; // Add padding to prevent content being hidden under face

  // Add toggle functionality
  header.addEventListener('click', () => {
    chatWindow.classList.toggle('chat-collapsed');
  });

  // Assemble chat window - add faceHolder directly to chatWindow, not header
  chatWindow.appendChild(header);
  chatWindow.appendChild(faceHolder);
  chatWindow.appendChild(messagesContainer);

  // Add to container
  chatContainer.appendChild(chatWindow);

  // Store reference
  chatWindows[power] = {
    element: chatWindow,
    messagesContainer: messagesContainer,
    isGlobal: isGlobal,
    seenMessages: new Set()
  };
}

// Modified to accumulate messages instead of resetting and only animate for new messages
/**
 * Updates chat windows with messages for the current phase
 * @param phase The current game phase containing messages
 * @param stepMessages Whether to animate messages one-by-word (true) or show all at once (false)
 */
export function updateChatWindows(phase: any, stepMessages = false) {
  // Exit early if no messages
  if (!phase.messages || !phase.messages.length) {
    console.log("No messages to display for this phase");
    gameState.messagesPlaying = false;
    return;
  }

  // Only show messages relevant to the current player (sent by them, to them, or global)
  const relevantMessages = phase.messages.filter(msg => {
    return (
      msg.sender === currentPower ||
      msg.recipient === currentPower ||
      msg.recipient === 'GLOBAL'
    );
  });

  // Sort messages by time sent
  relevantMessages.sort((a, b) => a.time_sent - b.time_sent);

  // Log message count but only in debug mode to reduce noise
  if (config.isDebugMode) {
    console.log(`Found ${relevantMessages.length} messages for player ${currentPower} in phase ${phase.name}`);
  }

  if (!stepMessages) {
    // Normal mode: show all messages at once
    relevantMessages.forEach(msg => {
      const isNew = addMessageToChat(msg, phase.name);
      if (isNew) {
        // Increment message counter and play sound on every third message
        messageCounter++;
        animateHeadNod(msg, (messageCounter % config.soundEffectFrequency === 0));
      }
    });
    gameState.messagesPlaying = false;
  } else {
    // Stepwise mode: show one message at a time, animating word-by-word
    gameState.messagesPlaying = true;
    let index = 0;

    // Store the start time for debugging
    const messageStartTime = Date.now();

    // Function to process the next message
    const showNext = () => {
      // If we're not playing or user has manually advanced, stop message animation
      if (!gameState.isPlaying && !config.isDebugMode) {
        console.log("Playback stopped, halting message animations");
        gameState.messagesPlaying = false;
        return;
      }

      // All messages have been displayed
      if (index >= relevantMessages.length) {
        if (config.isDebugMode) {
          console.log(`All messages displayed in ${Date.now() - messageStartTime}ms`);
        }

        gameState.messagesPlaying = false;

        // Only proceed if we're in playback mode and not speaking
        if (gameState.isPlaying && !gameState.isSpeaking) {
          if (gameState.gameData && gameState.gameData.phases) {
            const currentPhase = gameState.gameData.phases[gameState.phaseIndex];

            if (config.isDebugMode) {
              console.log(`Processing end of phase ${currentPhase.name}`);
            }

            // Show summary first if available
            if (currentPhase.summary?.trim()) {
              addToNewsBanner(`(${currentPhase.name}) ${currentPhase.summary}`);
            }

            // Get previous phase for animations
            const prevIndex = gameState.phaseIndex > 0 ? gameState.phaseIndex - 1 : null;
            const previousPhase = prevIndex !== null ? gameState.gameData.phases[prevIndex] : null;

            // Only schedule next phase if not already scheduled
            if (!gameState.nextPhaseScheduled) {
              gameState.nextPhaseScheduled = true;

              // Show animations for current phase's orders
              if (previousPhase) {
                if (config.isDebugMode) {
                  console.log(`Animating orders from ${previousPhase.name} to ${currentPhase.name}`);
                }

                // After animations complete, advance to next phase with longer delay
                gameState.playbackTimer = setTimeout(() => {
                  if (gameState.isPlaying) {
                    if (config.isDebugMode) {
                      console.log(`Animations complete, advancing from ${currentPhase.name}`);
                    }
                    advanceToNextPhase();
                  }
                }, config.playbackSpeed + config.animationDuration); // Wait for both summary and animations
              } else {
                // For first phase, use shorter delay since there are no animations
                if (config.isDebugMode) {
                  console.log(`First phase ${currentPhase.name} - no animations to wait for`);
                }

                gameState.playbackTimer = setTimeout(() => {
                  if (gameState.isPlaying) {
                    if (config.isDebugMode) {
                      console.log(`Advancing from first phase ${currentPhase.name}`);
                    }
                    advanceToNextPhase();
                  }
                }, config.playbackSpeed); // Only wait for summary, no animation delay
              }
            }
          }
        }
        return;
      }

      // Get the next message
      const msg = relevantMessages[index];

      // Only log in debug mode to reduce console noise
      if (config.isDebugMode) {
        console.log(`Displaying message ${index + 1}/${relevantMessages.length}: ${msg.sender} to ${msg.recipient}`);
      }

      // Function to call after message animation completes
      const onMessageComplete = () => {
        index++; // Only increment after animation completes

        // Schedule next message with proper delay
        setTimeout(showNext, config.playbackSpeed / 2);
      };

      // Add the message with word animation
      const isNew = addMessageToChat(msg, phase.name, true, onMessageComplete);

      // Handle non-new messages
      if (!isNew) {
        onMessageComplete(); // Skip animation for already seen messages
      } else if (!config.isDebugMode) {
        // Animate head and play sound for new messages
        messageCounter++;
        animateHeadNod(msg, (messageCounter % config.soundEffectFrequency === 0));
      }
    };

    // Start the message sequence with initial delay
    setTimeout(showNext, 50);
  }
}

// Modified to support word-by-word animation and callback
function addMessageToChat(msg, phaseName, animateWords = false, onComplete = null) {
  // Determine which chat window to use
  let targetPower;
  if (msg.recipient === 'GLOBAL') {
    targetPower = 'GLOBAL';
  } else {
    targetPower = msg.sender === currentPower ? msg.recipient : msg.sender;
  }
  if (!chatWindows[targetPower]) return false;

  // Create a unique ID for this message to avoid duplication
  const msgId = `${msg.sender}-${msg.recipient}-${msg.time_sent}-${msg.message}`;

  // Skip if we've already shown this message
  if (chatWindows[targetPower].seenMessages.has(msgId)) {
    return false; // Not a new message
  }

  // Mark as seen
  chatWindows[targetPower].seenMessages.add(msgId);

  const messagesContainer = chatWindows[targetPower].messagesContainer;
  const messageElement = document.createElement('div');

  // Style based on sender/recipient
  if (targetPower === 'GLOBAL') {
    // Global chat shows sender info
    const senderColor = msg.sender.toLowerCase();
    messageElement.className = 'chat-message message-incoming';

    // Add the header with the sender name immediately
    const headerSpan = document.createElement('span');
    headerSpan.style.fontWeight = 'bold';
    headerSpan.className = `power-${senderColor}`;
    headerSpan.textContent = `${msg.sender}: `;
    messageElement.appendChild(headerSpan);

    // Create a span for the message content that will be filled word by word
    const contentSpan = document.createElement('span');
    contentSpan.id = `msg-content-${msgId.replace(/[^a-zA-Z0-9]/g, '-')}`;
    messageElement.appendChild(contentSpan);

    // Add timestamp
    const timeDiv = document.createElement('div');
    timeDiv.className = 'message-time';
    timeDiv.textContent = phaseName;
    messageElement.appendChild(timeDiv);
  } else {
    // Private chat - outgoing or incoming style
    const isOutgoing = msg.sender === currentPower;
    messageElement.className = `chat-message ${isOutgoing ? 'message-outgoing' : 'message-incoming'}`;

    // Create content span
    const contentSpan = document.createElement('span');
    contentSpan.id = `msg-content-${msgId.replace(/[^a-zA-Z0-9]/g, '-')}`;
    messageElement.appendChild(contentSpan);

    // Add timestamp
    const timeDiv = document.createElement('div');
    timeDiv.className = 'message-time';
    timeDiv.textContent = phaseName;
    messageElement.appendChild(timeDiv);
  }

  // Add to container
  messagesContainer.appendChild(messageElement);

  // Scroll to bottom
  messagesContainer.scrollTop = messagesContainer.scrollHeight;

  if (animateWords) {
    // Start word-by-word animation
    const contentSpanId = `msg-content-${msgId.replace(/[^a-zA-Z0-9]/g, '-')}`;
    animateMessageWords(msg.message, contentSpanId, targetPower, messagesContainer, onComplete);
  } else {
    // Show entire message at once
    const contentSpan = messageElement.querySelector(`#msg-content-${msgId.replace(/[^a-zA-Z0-9]/g, '-')}`);
    if (contentSpan) {
      contentSpan.textContent = msg.message;
    }

    // If there's a completion callback, call it immediately for non-animated messages
    if (onComplete) {
      onComplete();
    }
  }

  return true; // This was a new message
}

// New function to animate message words one at a time
/**
 * Animates message text one word at a time
 * @param message The full message text to animate
 * @param contentSpanId The ID of the span element to animate within
 * @param targetPower The power the message is displayed for
 * @param messagesContainer The container holding the messages
 * @param onComplete Callback function to run when animation completes
 */
function animateMessageWords(message: string, contentSpanId: string, targetPower: string,
  messagesContainer: HTMLElement, onComplete: (() => void) | null) {
  const words = message.split(/\s+/);
  const contentSpan = document.getElementById(contentSpanId);
  if (!contentSpan) {
    // If span not found, still call onComplete to avoid breaking the game flow
    if (onComplete) onComplete();
    return;
  }

  // Clear any existing content
  contentSpan.textContent = '';
  let wordIndex = 0;

  // Function to add the next word
  const addNextWord = () => {
    if (wordIndex >= words.length) {
      // All words added - message is complete
      console.log(`Finished animating message with ${words.length} words in ${targetPower} chat`);

      // Add a slight delay after the last word for readability
      setTimeout(() => {
        if (onComplete) {
          onComplete(); // Call the completion callback
        }
      }, Math.min(config.playbackSpeed / 3, 150));

      return;
    }

    // Add space if not the first word
    if (wordIndex > 0) {
      contentSpan.textContent += ' ';
    }

    // Add the next word
    contentSpan.textContent += words[wordIndex];
    wordIndex++;

    // Calculate delay based on word length and playback speed
    // Longer words get slightly longer display time
    const wordLength = words[wordIndex - 1].length;
    const delay = Math.max(30, Math.min(120, config.playbackSpeed / 10 * (wordLength / 4)));
    setTimeout(addNextWord, delay);

    // Scroll to ensure newest content is visible
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  };

  // Start animation
  addNextWord();
}

// Modified to support conditional sound effects
function animateHeadNod(msg, playSoundEffect = true) {
  // Determine which chat window's head to animate
  let targetPower;
  if (msg.recipient === 'GLOBAL') {
    targetPower = 'GLOBAL';
  } else {
    targetPower = msg.sender === currentPower ? msg.recipient : msg.sender;
  }

  const chatWindow = chatWindows[targetPower]?.element;
  if (!chatWindow) return;

  // Find the face image and animate it
  const img = chatWindow.querySelector(`#face-img-${targetPower}`);
  if (!img) return;

  img.dataset.animating = 'true';

  // Choose a random animation type for variety
  const animationType = Math.floor(Math.random() * 4);

  let animation;

  switch (animationType) {
    case 0: // Nod animation
      animation = img.animate([
        { transform: 'rotate(0deg) scale(1)' },
        { transform: 'rotate(15deg) scale(1.1)' },
        { transform: 'rotate(-10deg) scale(1.05)' },
        { transform: 'rotate(5deg) scale(1.02)' },
        { transform: 'rotate(0deg) scale(1)' }
      ], {
        duration: 600,
        easing: 'ease-in-out'
      });
      break;

    case 1: // Bounce animation
      animation = img.animate([
        { transform: 'translateY(0) scale(1)' },
        { transform: 'translateY(-8px) scale(1.15)' },
        { transform: 'translateY(3px) scale(0.95)' },
        { transform: 'translateY(-2px) scale(1.05)' },
        { transform: 'translateY(0) scale(1)' }
      ], {
        duration: 700,
        easing: 'ease-in-out'
      });
      break;

    case 2: // Shake animation
      animation = img.animate([
        { transform: 'translate(0, 0) rotate(0deg)' },
        { transform: 'translate(-5px, -3px) rotate(-5deg)' },
        { transform: 'translate(5px, 2px) rotate(5deg)' },
        { transform: 'translate(-5px, 1px) rotate(-3deg)' },
        { transform: 'translate(0, 0) rotate(0deg)' }
      ], {
        duration: 500,
        easing: 'ease-in-out'
      });
      break;

    case 3: // Pulse animation
      animation = img.animate([
        { transform: 'scale(1)', boxShadow: '0 0 0 0 rgba(255,255,255,0.7)' },
        { transform: 'scale(1.2)', boxShadow: '0 0 0 10px rgba(255,255,255,0)' },
        { transform: 'scale(1)', boxShadow: '0 0 0 0 rgba(255,255,255,0)' }
      ], {
        duration: 800,
        easing: 'ease-out'
      });
      break;
  }

  animation.onfinish = () => {
    img.dataset.animating = 'false';
  };

  // Trigger random snippet only if playSoundEffect is true
  if (playSoundEffect) {
    playRandomSoundEffect();
  }
}

// Generate a 3D face icon for chat windows with higher contrast
async function generateFaceIcon(power) {
  if (faceIconCache[power]) {
    return faceIconCache[power];
  }

  // Even larger renderer size for better quality
  const offWidth = 192, offHeight = 192; // Increased from 128x128 to 192x192
  const offRenderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  offRenderer.setSize(offWidth, offHeight);
  offRenderer.setPixelRatio(1);

  // Scene
  const offScene = new THREE.Scene();
  offScene.background = null;

  // Camera
  const offCamera = new THREE.PerspectiveCamera(45, offWidth / offHeight, 0.1, 1000);
  offCamera.position.set(0, 0, 50);

  // Power-specific colors with higher contrast/saturation
  const colorMap = {
    'GLOBAL': 0xf5f5f5, // Brighter white
    'AUSTRIA': 0xff0000, // Brighter red
    'ENGLAND': 0x0000ff, // Brighter blue
    'FRANCE': 0x00bfff, // Brighter cyan
    'GERMANY': 0x1a1a1a, // Darker gray for better contrast
    'ITALY': 0x00cc00, // Brighter green
    'RUSSIA': 0xe0e0e0, // Brighter gray
    'TURKEY': 0xffcc00  // Brighter yellow
  };
  const headColor = colorMap[power] || 0x808080;

  // Larger head geometry
  const headGeom = new THREE.BoxGeometry(20, 20, 20); // Increased from 16x16x16
  const headMat = new THREE.MeshStandardMaterial({ color: headColor });
  const headMesh = new THREE.Mesh(headGeom, headMat);
  offScene.add(headMesh);

  // Create outline for better visibility (a slightly larger black box behind)
  const outlineGeom = new THREE.BoxGeometry(22, 22, 19);
  const outlineMat = new THREE.MeshBasicMaterial({ color: 0x000000 });
  const outlineMesh = new THREE.Mesh(outlineGeom, outlineMat);
  outlineMesh.position.z = -2; // Place it behind the head
  offScene.add(outlineMesh);

  // Larger eyes with better contrast
  const eyeGeom = new THREE.BoxGeometry(3.5, 3.5, 3.5); // Increased from 2.5x2.5x2.5
  const eyeMat = new THREE.MeshStandardMaterial({ color: 0x000000 });
  const leftEye = new THREE.Mesh(eyeGeom, eyeMat);
  leftEye.position.set(-4.5, 2, 10); // Adjusted position
  offScene.add(leftEye);
  const rightEye = new THREE.Mesh(eyeGeom, eyeMat);
  rightEye.position.set(4.5, 2, 10); // Adjusted position
  offScene.add(rightEye);

  // Add a simple mouth
  const mouthGeom = new THREE.BoxGeometry(8, 1.5, 1);
  const mouthMat = new THREE.MeshBasicMaterial({ color: 0x000000 });
  const mouth = new THREE.Mesh(mouthGeom, mouthMat);
  mouth.position.set(0, -3, 10);
  offScene.add(mouth);

  // Brighter lighting for better contrast
  const light = new THREE.DirectionalLight(0xffffff, 1.2); // Increased intensity
  light.position.set(0, 20, 30);
  offScene.add(light);

  // Add more lights for better definition
  const fillLight = new THREE.DirectionalLight(0xffffff, 0.5);
  fillLight.position.set(-20, 0, 20);
  offScene.add(fillLight);

  offScene.add(new THREE.AmbientLight(0xffffff, 0.4)); // Slightly brighter ambient

  // Slight head rotation
  headMesh.rotation.y = Math.PI / 6; // More pronounced angle

  // Render to a texture
  const renderTarget = new THREE.WebGLRenderTarget(offWidth, offHeight);
  offRenderer.setRenderTarget(renderTarget);
  offRenderer.render(offScene, offCamera);

  // Get pixels
  const pixels = new Uint8Array(offWidth * offHeight * 4);
  offRenderer.readRenderTargetPixels(renderTarget, 0, 0, offWidth, offHeight, pixels);

  // Convert to canvas
  const canvas = document.createElement('canvas');
  canvas.width = offWidth;
  canvas.height = offHeight;
  const ctx = canvas.getContext('2d');
  const imageData = ctx.createImageData(offWidth, offHeight);
  imageData.data.set(pixels);

  // Flip image (WebGL coordinate system is inverted)
  flipImageDataVertically(imageData, offWidth, offHeight);
  ctx.putImageData(imageData, 0, 0);

  // Get data URL
  const dataURL = canvas.toDataURL('image/png');
  faceIconCache[power] = dataURL;

  // Cleanup
  offRenderer.dispose();
  renderTarget.dispose();

  return dataURL;
}

// Add a subtle idle animation for faces
function idleAnimation(img) {
  if (img.dataset.animating === 'true') return;

  img.dataset.animating = 'true';

  const animation = img.animate([
    { transform: 'rotate(0deg) scale(1)' },
    { transform: 'rotate(-2deg) scale(0.98)' },
    { transform: 'rotate(0deg) scale(1)' }
  ], {
    duration: 1500,
    easing: 'ease-in-out'
  });

  animation.onfinish = () => {
    img.dataset.animating = 'false';
  };
}

// Helper to flip image data vertically
function flipImageDataVertically(imageData, width, height) {
  const bytesPerRow = width * 4;
  const temp = new Uint8ClampedArray(bytesPerRow);
  for (let y = 0; y < height / 2; y++) {
    const topOffset = y * bytesPerRow;
    const bottomOffset = (height - y - 1) * bytesPerRow;
    temp.set(imageData.data.slice(topOffset, topOffset + bytesPerRow));
    imageData.data.set(imageData.data.slice(bottomOffset, bottomOffset + bytesPerRow), topOffset);
    imageData.data.set(temp, bottomOffset);
  }
}

// --- NEW: Function to play a random sound effect ---
function playRandomSoundEffect() {
  // List all the sound snippet filenames in assets/sounds
  const soundEffects = [
    'snippet_2.mp3',
    'snippet_3.mp3',
    'snippet_4.mp3',
    'snippet_9.mp3',
    'snippet_10.mp3',
    'snippet_11.mp3',
    'snippet_12.mp3',
    'snippet_13.mp3',
    'snippet_14.mp3',
    'snippet_15.mp3',
    'snippet_16.mp3',
    'snippet_17.mp3',
  ];
  // Pick one at random
  const chosen = soundEffects[Math.floor(Math.random() * soundEffects.length)];

  // Create an <audio> and play
  const audio = new Audio(`./sounds/${chosen}`);
  audio.play().catch(err => {
    // In case of browser auto-play restrictions, you may see warnings in console
    console.warn("Audio play was interrupted:", err);
  });
}

/**
 * Appends text to the scrolling news banner.
 * If the banner is at its default text or empty, replace it entirely.
 * Otherwise, just append " | " + newText.
 * @param newText Text to add to the news banner
 */
export function addToNewsBanner(newText: string): void {
  const bannerEl = document.getElementById('news-banner-content');
  if (!bannerEl) {
    console.warn("News banner element not found");
    return;
  }

  if (config.isDebugMode) {
    console.log(`Adding to news banner: "${newText}"`);
  }

  // Add a fade-out transition
  bannerEl.style.transition = 'opacity 0.3s ease-out';
  bannerEl.style.opacity = '0';

  setTimeout(() => {
    // If the banner only has the default text or is empty, replace it
    if (
      bannerEl.textContent?.trim() === 'Diplomatic actions unfolding...' ||
      bannerEl.textContent?.trim() === ''
    ) {
      bannerEl.textContent = newText;
    } else {
      // Otherwise append with a separator
      bannerEl.textContent += '  |  ' + newText;
    }

    // Fade back in
    bannerEl.style.opacity = '1';
  }, 300);
}
