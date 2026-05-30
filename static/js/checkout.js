(function () {
  "use strict";

  const form = document.getElementById("checkout-form");
  if (!form) return;

  const overlay = document.getElementById("loading-overlay");
  const payNowBtn = document.getElementById("pay-now-btn");
  const placeOrderBtn = document.getElementById("place-order-btn");

  const upiSection = document.getElementById("upi-section");
  const cardSection = document.getElementById("card-section");

  function showOverlay() {
    overlay && overlay.classList.remove("hidden");
    payNowBtn && (payNowBtn.disabled = true);
    placeOrderBtn && (placeOrderBtn.disabled = true);
  }

  function hideOverlay() {
    overlay && overlay.classList.add("hidden");
    payNowBtn && (payNowBtn.disabled = false);
    placeOrderBtn && (placeOrderBtn.disabled = false);
  }

  function getPaymentMethod() {
    const checked = form.querySelector("input[name='payment_method']:checked");
    return checked ? checked.value : "";
  }

  function togglePaymentSections() {
    const method = getPaymentMethod();
    if (upiSection) upiSection.classList.toggle("hidden", method !== "upi");
    if (cardSection) cardSection.classList.toggle("hidden", method !== "card");
  }

  function setError(field, message) {
    const el = form.querySelector(`[data-error-for="${field}"]`);
    if (el) el.textContent = message || "";
  }

  function clearErrors() {
    form.querySelectorAll("[data-error-for]").forEach((el) => (el.textContent = ""));
  }

  function valueOf(id) {
    const el = document.getElementById(id);
    return el ? (el.value || "").trim() : "";
  }

  function validate() {
    clearErrors();
    let ok = true;

    const fullName = valueOf("full_name");
    const phone = valueOf("phone").replace(/\s+/g, "");
    const email = valueOf("email");
    const address = valueOf("address");
    const city = valueOf("city");
    const state = valueOf("state");
    const pincode = valueOf("pincode").replace(/\s+/g, "");
    const paymentMethod = getPaymentMethod();

    if (!fullName) {
      ok = false;
      setError("full_name", "Full name is required.");
    } else if (!/^[A-Za-z ]+$/.test(fullName)) {
      ok = false;
      setError("full_name", "Only alphabets and spaces are allowed.");
    }

    if (!/^\d{10}$/.test(phone)) {
      ok = false;
      setError("phone", "Phone number must be exactly 10 digits.");
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      ok = false;
      setError("email", "Please enter a valid email address.");
    }

    if (!address) {
      ok = false;
      setError("address", "Address is required.");
    } else if (address.length < 10) {
      ok = false;
      setError("address", "Address must be at least 10 characters.");
    }

    if (!city) {
      ok = false;
      setError("city", "City is required.");
    }
    if (!state) {
      ok = false;
      setError("state", "State is required.");
    }

    if (!/^\d{6}$/.test(pincode)) {
      ok = false;
      setError("pincode", "Pincode must be exactly 6 digits.");
    }

    if (!paymentMethod) {
      ok = false;
      setError("payment_method", "Please select a payment method.");
    } else if (paymentMethod === "upi") {
      const upi = valueOf("upi_id");
      if (!upi) {
        ok = false;
        setError("upi_id", "Please enter your UPI ID.");
      }
    } else if (paymentMethod === "card") {
      const cardName = valueOf("card_name");
      const cardNumber = valueOf("card_number").replace(/\s+/g, "");
      const cardExpiry = valueOf("card_expiry");
      const cardCvv = valueOf("card_cvv");

      if (!cardName) {
        ok = false;
        setError("card_name", "Name on card is required.");
      }
      if (!/^\d{12,19}$/.test(cardNumber)) {
        ok = false;
        setError("card_number", "Please enter a valid card number.");
      }
      if (!/^(0[1-9]|1[0-2])\/\d{2}$/.test(cardExpiry)) {
        ok = false;
        setError("card_expiry", "Expiry must be in MM/YY format.");
      }
      if (!/^\d{3,4}$/.test(cardCvv)) {
        ok = false;
        setError("card_cvv", "Please enter a valid CVV.");
      }
    }

    return ok;
  }

  // Init
  togglePaymentSections();
  form.querySelectorAll("input[name='payment_method']").forEach((el) => {
    el.addEventListener("change", togglePaymentSections);
  });

  // Pay Now: simulate processing with loader (no real gateway wired)
  if (payNowBtn) {
    payNowBtn.addEventListener("click", function () {
      if (!validate()) return;
      showOverlay();
      window.setTimeout(hideOverlay, 1200);
    });
  }

  // Place Order: validate and show loader until navigation
  form.addEventListener("submit", function (e) {
    if (!validate()) {
      e.preventDefault();
      return;
    }
    showOverlay();
  });
})();

