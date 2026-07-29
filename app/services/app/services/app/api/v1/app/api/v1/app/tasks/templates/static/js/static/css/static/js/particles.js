/**
 * Генератор анимированных частиц на фоне.
 */
class ParticleSystem {
    constructor() {
        this.container = document.getElementById('particles');
        if (!this.container) return;
        this.particles = [];
        this.maxParticles = 30;
        this.init();
    }

    init() {
        for (let i = 0; i < this.maxParticles; i++) {
            this.createParticle();
        }
    }

    createParticle() {
        const particle = document.createElement('div');
        particle.className = 'particle';

        const size = Math.random() * 8 + 4;
        const x = Math.random() * 100;
        const y = Math.random() * 100;
        const duration = Math.random() * 6 + 4;
        const delay = Math.random() * 6;

        particle.style.width = `${size}px`;
        particle.style.height = `${size}px`;
        particle.style.left = `${x}%`;
        particle.style.top = `${y}%`;
        particle.style.animationDuration = `${duration}s`;
        particle.style.animationDelay = `${delay}s`;

        if (Math.random() > 0.5) {
            particle.style.background = 'var(--pink-300)';
        }

        this.container.appendChild(particle);
        this.particles.push(particle);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new ParticleSystem();

    // Мобильное меню
    const burgerBtn = document.getElementById('burgerBtn');
    const sidebar = document.getElementById('sidebar');

    if (burgerBtn && sidebar) {
        burgerBtn.addEventListener('click', () => {
            sidebar.classList.toggle('open');
        });
    }
});
