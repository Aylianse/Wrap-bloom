/* ════════════════════════════════════════════
   Wrap & Bloom — main.js
   Navigation: hamburger + dropdown logic
════════════════════════════════════════════ */

(function () {
  "use strict";

  /* ── Element refs ── */
  const hamburger = document.getElementById("nav-hamburger");
  const navLinks  = document.getElementById("nav-links");
  const overlay   = document.getElementById("nav-overlay");
  const dropdown  = document.getElementById("nav-categories");
  const dropBtn   = document.getElementById("nav-categories-btn");

  /* ══════════════════════════════════════════
     Hamburger / Mobile Drawer
  ══════════════════════════════════════════ */
  function openDrawer() {
    navLinks.classList.add("navbar__links--open");
    hamburger.classList.add("navbar__hamburger--open");
    overlay.classList.add("navbar__overlay--visible");
    hamburger.setAttribute("aria-expanded", "true");
    document.body.style.overflow = "hidden";
  }

  function closeDrawer() {
    navLinks.classList.remove("navbar__links--open");
    hamburger.classList.remove("navbar__hamburger--open");
    overlay.classList.remove("navbar__overlay--visible");
    hamburger.setAttribute("aria-expanded", "false");
    document.body.style.overflow = "";
    closeDropdown();   // also collapse dropdown when drawer closes
  }

  if (hamburger) {
    hamburger.addEventListener("click", function () {
      const isOpen = navLinks.classList.contains("navbar__links--open");
      isOpen ? closeDrawer() : openDrawer();
    });
  }

  if (overlay) {
    overlay.addEventListener("click", closeDrawer);
  }

  /* ══════════════════════════════════════════
     Product Categories Dropdown
  ══════════════════════════════════════════ */
  function openDropdown() {
    if (!dropdown) return;
    dropdown.classList.add("navbar__dropdown--open");
    dropBtn && dropBtn.setAttribute("aria-expanded", "true");
  }

  function closeDropdown() {
    if (!dropdown) return;
    dropdown.classList.remove("navbar__dropdown--open");
    dropBtn && dropBtn.setAttribute("aria-expanded", "false");
  }

  function toggleDropdown() {
    dropdown.classList.contains("navbar__dropdown--open")
      ? closeDropdown()
      : openDropdown();
  }

  if (dropBtn) {
    dropBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      toggleDropdown();
    });
  }

  /* Close dropdown when clicking anywhere outside */
  document.addEventListener("click", function (e) {
    if (dropdown && !dropdown.contains(e.target)) {
      closeDropdown();
    }
  });

  /* ══════════════════════════════════════════
     Keyboard Accessibility
  ══════════════════════════════════════════ */
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      closeDropdown();
      closeDrawer();
    }
  });

  /* ══════════════════════════════════════════
     Close drawer on desktop resize
  ══════════════════════════════════════════ */
  window.addEventListener("resize", function () {
    if (window.innerWidth > 768) {
      closeDrawer();
    }
  });

  /* ══════════════════════════════════════════
     Navbar scroll shadow
  ══════════════════════════════════════════ */
  const navbar = document.getElementById("main-navbar");
  if (navbar) {
    window.addEventListener("scroll", function () {
      navbar.style.boxShadow = window.scrollY > 10
        ? "0 4px 24px rgba(0,0,0,.6)"
        : "";
    }, { passive: true });
  }

})();
