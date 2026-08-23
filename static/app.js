document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
        if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
});

const navToggle = document.querySelector(".nav-toggle");
const mainNav = document.querySelector(".main-nav");
if (navToggle && mainNav) {
    navToggle.addEventListener("click", () => {
        const open = mainNav.classList.toggle("is-open");
        navToggle.setAttribute("aria-expanded", String(open));
    });
}
