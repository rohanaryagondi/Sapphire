// Custom homepage welcome screen customization
(function() {
  'use strict';

  // Function to inject custom title and subtitle
  function injectWelcomeContent() {
    // Wait for the welcome screen to be available
    const checkInterval = setInterval(() => {
      // Check if we're on the chat page (messages exist)
      const hasMessages = document.querySelector('[class*="MessageContainer"]') ||
                         document.querySelector('[class*="Message-"]') ||
                         document.querySelector('.step');

      // Only show title on homepage (no messages)
      if (hasMessages) {
        clearInterval(checkInterval);
        return;
      }

      // Try multiple selectors to find the welcome/starter area
      const welcomeContainer =
        document.querySelector('[class*="WelcomeScreen"]') ||
        document.querySelector('[class*="Starter"]')?.parentElement?.parentElement ||
        document.querySelector('main > div:first-child') ||
        document.querySelector('[class*="MuiBox-root"]:has(img[alt*="logo"])');

      if (welcomeContainer && !document.getElementById('custom-welcome-title')) {
        clearInterval(checkInterval);

        // Create custom title container
        const titleContainer = document.createElement('div');
        titleContainer.id = 'custom-welcome-title';
        titleContainer.style.cssText = `
          text-align: center;
          margin: 0 auto;
          padding: 0 1rem;
        `;

        // Create main title
        const title = document.createElement('h1');
        title.textContent = 'Sapphire';
        title.style.cssText = `
          font-size: 2rem;
          font-weight: 300;
          letter-spacing: 0.02em;
          margin: 0 0 0.5rem 0;
          color: var(--text-primary, #e0e0e0);
        `;

        // Create subtitle
        const subtitle = document.createElement('p');
        subtitle.textContent = 'CNS decision firm — the dossier, the roundtable, the spread';
        subtitle.style.cssText = `
          font-size: 1.2rem;
          font-weight: 300;
          margin: 0.5rem 0 2rem 0;
          opacity: 0.7;
          color: var(--text-secondary, #a0a0a0);
        `;

        titleContainer.appendChild(title);
        titleContainer.appendChild(subtitle);

        // Find the logo image
        const logoImg = welcomeContainer.querySelector('img[src*="logo"]');

        if (logoImg) {
          // Insert after the logo
          logoImg.parentNode.insertBefore(titleContainer, logoImg.nextSibling);
        } else {
          // If no logo found, insert at the beginning
          welcomeContainer.insertBefore(titleContainer, welcomeContainer.firstChild);
        }

        console.log('Custom welcome content injected successfully');
      }
    }, 100); // Check every 100ms

    // Stop checking after 10 seconds
    setTimeout(() => clearInterval(checkInterval), 10000);
  }

  // Run when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectWelcomeContent);
  } else {
    injectWelcomeContent();
  }

  // Also watch for React re-renders
  const observer = new MutationObserver(() => {
    // Check if we're on the chat page (messages exist)
    const hasMessages = document.querySelector('[class*="MessageContainer"]') ||
                       document.querySelector('[class*="Message-"]') ||
                       document.querySelector('.step');

    // Remove title if we navigate to chat page
    if (hasMessages) {
      const existingTitle = document.getElementById('custom-welcome-title');
      if (existingTitle) {
        existingTitle.remove();
      }
    } else if (!document.getElementById('custom-welcome-title')) {
      // Only inject if on homepage and the custom title doesn't exist yet
      injectWelcomeContent();
    }
  });

  // Start observing when body is available
  if (document.body) {
    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
  }
})();
