/**
 * Foundry – User Dashboard
 * GSAP animations, counters, interactivity
 */

document.addEventListener('DOMContentLoaded', function() {
    'use strict';

    // ============================================================
    // 1. PAGE REVEAL
    // ============================================================
    gsap.from('.main-content', {
        opacity: 0,
        y: 20,
        duration: 0.8,
        ease: 'power2.out'
    });

    // ============================================================
    // 2. STATISTICS COUNTERS (with stagger)
    // ============================================================
    const statNumbers = document.querySelectorAll('.stat-number');
    const statCards = document.querySelectorAll('.stat-card');

    // Animate cards stagger
    gsap.from(statCards, {
        scale: 0.95,
        opacity: 0,
        y: 30,
        duration: 0.6,
        stagger: 0.1,
        ease: 'back.out(1.2)',
        delay: 0.3
    });

    // Counter animation
    function animateCounter(el) {
        const target = parseInt(el.getAttribute('data-target'), 10);
        const duration = 1200;
        const startTime = performance.now();

        function updateCounter(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            // Ease out cubic
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = Math.round(eased * target);
            el.textContent = current;

            if (progress < 1) {
                requestAnimationFrame(updateCounter);
            } else {
                el.textContent = target;
            }
        }
        requestAnimationFrame(updateCounter);
    }

    // Start counters after card animation
    setTimeout(() => {
        statNumbers.forEach(el => animateCounter(el));
    }, 900);

    // ============================================================
    // 3. SIDEBAR MOBILE TOGGLE
    // ============================================================
    const mobileBtn = document.getElementById('mobileMenuBtn');
    const sidebar = document.querySelector('.sidebar');

    mobileBtn.addEventListener('click', function() {
        const isOpen = sidebar.classList.toggle('open');
        this.setAttribute('aria-expanded', isOpen);
    });

    // Close sidebar on outside click (optional)
    document.addEventListener('click', function(e) {
        if (window.innerWidth <= 992) {
            if (!sidebar.contains(e.target) && !mobileBtn.contains(e.target)) {
                sidebar.classList.remove('open');
                mobileBtn.setAttribute('aria-expanded', 'false');
            }
        }
    });

    // ============================================================
    // 4. BOOK CARDS STAGGER ON LOAD
    // ============================================================
    const bookCards = document.querySelectorAll('.book-card');
    gsap.from(bookCards, {
        opacity: 0,
        y: 30,
        duration: 0.5,
        stagger: 0.08,
        ease: 'power2.out',
        delay: 0.6
    });

    // ============================================================
    // 5. KNOWLEDGE CARDS STAGGER
    // ============================================================
    const knowledgeCards = document.querySelectorAll('.knowledge-card');
    gsap.from(knowledgeCards, {
        opacity: 0,
        scale: 0.92,
        duration: 0.5,
        stagger: 0.07,
        ease: 'back.out(1.4)',
        delay: 0.8
    });

    // ============================================================
    // 6. TIMELINE ITEMS STAGGER
    // ============================================================
    const timelineItems = document.querySelectorAll('.timeline-item');
    gsap.from(timelineItems, {
        opacity: 0,
        x: -20,
        duration: 0.4,
        stagger: 0.1,
        ease: 'power2.out',
        delay: 0.7
    });

    // ============================================================
    // 7. PROGRESS RING ANIMATION (on load)
    // ============================================================
    const ringFg = document.querySelector('.ring-fg');
    if (ringFg) {
        // The stroke-dashoffset is already set in HTML (130.69)
        // We'll animate it from full to target
        const circumference = 326.73;
        const currentOffset = parseFloat(ringFg.getAttribute('stroke-dashoffset')) || 130.69;
        // Start from full (no dash)
        ringFg.style.strokeDashoffset = circumference;
        gsap.to(ringFg, {
            strokeDashoffset: currentOffset,
            duration: 1.2,
            ease: 'power2.inOut',
            delay: 1.0
        });
    }

    // ============================================================
    // 8. HOVER LIFT (using GSAP for smoothness) – added via CSS too
    // ============================================================
    // But we can add micro interactions with GSAP on hover
    const hoverElements = document.querySelectorAll(
        '.stat-card, .book-card, .knowledge-card, .quick-btn, .premium-btn'
    );
    hoverElements.forEach(el => {
        el.addEventListener('mouseenter', function() {
            gsap.to(this, {
                scale: 1.02,
                duration: 0.2,
                ease: 'power1.out',
                overwrite: 'auto'
            });
        });
        el.addEventListener('mouseleave', function() {
            gsap.to(this, {
                scale: 1,
                duration: 0.3,
                ease: 'power1.out',
                overwrite: 'auto'
            });
        });
    });

    // ============================================================
    // 9. SIDEBAR NAV ACTIVE STATE (demo)
    // ============================================================
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            navLinks.forEach(l => l.classList.remove('active'));
            this.classList.add('active');
            // Close mobile sidebar if open
            if (window.innerWidth <= 992) {
                sidebar.classList.remove('open');
                mobileBtn.setAttribute('aria-expanded', 'false');
            }
        });
    });

    // ============================================================
    // 10. SEARCH KEYBOARD SHORTCUT (⌘K)
    // ============================================================
    document.addEventListener('keydown', function(e) {
        if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
            e.preventDefault();
            const searchInput = document.querySelector('.search-input');
            if (searchInput) {
                searchInput.focus();
                // Select all text
                searchInput.select();
            }
        }
    });

    // ============================================================
    // 11. NOTIFICATION BUTTON (simple demo)
    // ============================================================
    const notifBtn = document.querySelector('.notif-btn');
    if (notifBtn) {
        notifBtn.addEventListener('click', function() {
            // just a micro feedback
            gsap.timeline()
                .to(this, { scale: 0.9, duration: 0.1, ease: 'power1.in' })
                .to(this, { scale: 1, duration: 0.2, ease: 'power1.out' });
            // could show a notification panel later
        });
    }

    // ============================================================
    // 12. CONTINUE BUTTON MICRO
    // ============================================================
    document.querySelectorAll('.book-continue').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            gsap.timeline()
                .to(this, { x: 4, duration: 0.15, ease: 'power1.out' })
                .to(this, { x: 0, duration: 0.2, ease: 'power1.inOut' });
        });
    });

    console.log('Foundry Dashboard – GSAP animations ready');
});