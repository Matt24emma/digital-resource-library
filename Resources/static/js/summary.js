
console.log("summary.js loaded");
document.addEventListener("DOMContentLoaded", () => {
  // -------------------------
  // Lucide icons
  // -------------------------

  lucide.createIcons();

  // -------------------------
  // Hero animation
  // -------------------------

  gsap.from(".title", {
    duration: 1,
    opacity: 0,
    scale: 1.2,
    ease: "power2.out",
  });

  gsap.from(".card", {
    y: 60,
    opacity: 0,
    duration: 1,
    stagger: 0.2,
    ease: "power3.out",
  });

  gsap.from(".hero p", {
    y: 30,
    opacity: 0,
    duration: 1,
    delay: 0.3,
  });

  // -------------------------
  // Hero text switcher
  // -------------------------

  const hero = document.getElementById("hero");

  if (!hero) {
    return;
  }

  const texts = [
    "Turn Knowledge Into Beautiful Memories",
    "...Capture Ideas That Matter",
    "Build Your Personal Knowledge Library...",
  ];

  const colors = ["#22C55E", "#3B82F6", "#F59E0B"];

  let index = 0;

  function switchHero() {
    gsap.to(hero, {
      opacity: 0,
      y: -15,
      duration: 0.4,
      ease: "power2.in",

      onComplete: () => {
        index = (index + 1) % texts.length;

        hero.textContent = texts[index];

        hero.style.color = colors[index];

        gsap.fromTo(
          hero,

          {
            opacity: 0,
            y: 15,
          },

          {
            opacity: 1,
            y: 0,
            duration: 0.6,
            ease: "power3.out",
          },
        );
      },
    });
  }

  setInterval(switchHero, 5000);

  // -------------------------
  // Initial hero animation
  // -------------------------

  gsap.fromTo(
    hero,

    {
      opacity: 0,
      y: 15,
      scale: 0.97,
    },

    {
      opacity: 1,
      y: 0,
      scale: 1,
      duration: 0.6,
      ease: "power3.out",
    },
  );
});










// ============================================
// Overflow Debugger – find elements that cause horizontal scroll
// ============================================
(function() {
    'use strict';

    // ---------- Configuration ----------
    const HIGHLIGHT_OVERFLOW = true;   // set to false to only log
    const BORDER_COLOR = 'red';
    const BORDER_WIDTH = '3px';
    // -----------------------------------

    function debugOverflow() {
        const allElements = document.querySelectorAll('*');
        const overflowed = [];

        allElements.forEach(el => {
            // Skip elements that are hidden or have no dimensions
            const rect = el.getBoundingClientRect();
            if (rect.width === 0 && rect.height === 0) return;

            // Check for horizontal overflow (scrollWidth > clientWidth)
            const hasOverflowX = el.scrollWidth > el.clientWidth;
            // Check for vertical overflow (scrollHeight > clientHeight)
            const hasOverflowY = el.scrollHeight > el.clientHeight;

            // Also detect if the element itself causes the body to overflow
            // by checking if its bounding rect exceeds the viewport
            const exceedsViewportX = rect.right > window.innerWidth || rect.left < 0;
            const exceedsViewportY = rect.bottom > window.innerHeight || rect.top < 0;

            if (hasOverflowX || hasOverflowY || exceedsViewportX || exceedsViewportY) {
                overflowed.push({
                    element: el,
                    tag: el.tagName,
                    class: el.className || '(no class)',
                    id: el.id || '(no id)',
                    scrollWidth: el.scrollWidth,
                    clientWidth: el.clientWidth,
                    scrollHeight: el.scrollHeight,
                    clientHeight: el.clientHeight,
                    rect: rect,
                    hasOverflowX: hasOverflowX,
                    hasOverflowY: hasOverflowY,
                    exceedsViewportX: exceedsViewportX,
                    exceedsViewportY: exceedsViewportY
                });

                // Highlight the element with a red border
                if (HIGHLIGHT_OVERFLOW) {
                    el.style.outline = `${BORDER_WIDTH} solid ${BORDER_COLOR}`;
                    el.style.outlineOffset = '2px';
                }
            }
        });

        // Log results to the console
        if (overflowed.length === 0) {
            console.log('✅ No overflowing elements found!');
        } else {
            console.warn(`🚨 Found ${overflowed.length} element(s) with overflow or exceeding viewport:`);
            overflowed.forEach((item, index) => {
                console.group(`Element #${index + 1}`);
                console.log('Tag:', item.tag);
                console.log('Class:', item.class);
                console.log('ID:', item.id);
                console.log('Scroll width/height:', item.scrollWidth, 'x', item.scrollHeight);
                console.log('Client width/height:', item.clientWidth, 'x', item.clientHeight);
                console.log('Bounding rect:', item.rect);
                console.log('Overflow X:', item.hasOverflowX);
                console.log('Overflow Y:', item.hasOverflowY);
                console.log('Exceeds viewport X:', item.exceedsViewportX);
                console.log('Exceeds viewport Y:', item.exceedsViewportY);
                console.log('Element:', item.element);
                console.groupEnd();
            });

            // Also log a summary table for quick view
            console.table(overflowed.map(item => ({
                Tag: item.tag,
                Class: item.class,
                ID: item.id,
                'Scroll W/H': `${item.scrollWidth}x${item.scrollHeight}`,
                'Client W/H': `${item.clientWidth}x${item.clientHeight}`,
                'Overflow X': item.hasOverflowX,
                'Overflow Y': item.hasOverflowY,
                'Exceeds X': item.exceedsViewportX,
                'Exceeds Y': item.exceedsViewportY
            })));
        }

        return overflowed;
    }

    // ---------- Auto-run on load (optional) ----------
    // Uncomment the next line if you want it to run automatically
    // window.addEventListener('load', debugOverflow);

    // ---------- Expose to global scope for manual use ----------
    window.debugOverflow = debugOverflow;

    // ---------- Keyboard shortcut (Shift+O) ----------
    document.addEventListener('keydown', function(e) {
        if (e.shiftKey && (e.key === 'O' || e.key === 'o')) {
            e.preventDefault();
            console.clear();
            debugOverflow();
        }
    });

    console.log('🔍 Overflow debugger loaded. Press Shift+O to scan for overflow. Or call debugOverflow() in console.');
})();